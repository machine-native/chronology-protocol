// Cmod A7-35T top level: UART <-> SHA-256d nonce scanner.
//
// Wire protocol, deliberately byte-oriented and stateless enough to drive from a
// 40-line Python script:
//
//   host -> FPGA   0x57 ('W') then 48 bytes of work, big-endian:
//                    midstate  32 B   (host-computed over header[0:64])
//                    tail      12 B   (header[64:76])
//                    nonce_start 4 B
//                  scanning starts immediately and runs to 2^32 wrap
//   host -> FPGA   0x53 ('S')  stop/abort
//   host -> FPGA   0x50 ('P')  ping -> replies 0x4B ('K')
//
//   FPGA -> host   0x46 ('F') then 4 bytes nonce, then 32 bytes digest
//                  (a candidate; the HOST applies the exact target test)
//   FPGA -> host   0x45 ('E')  range exhausted
//
// The FPGA never decides validity. It reports candidates whose trailing digest
// words are zero; the host re-checks against the compact target using the same
// tested software path that validates real blocks.
`default_nettype none

module miner_top #(
    parameter integer CLK_HZ     = 12_000_000,   // Cmod A7 on-board oscillator
    parameter integer BAUD       = 115200,
    parameter integer ZERO_WORDS = 1
) (
    input  wire clk,
    // Named for what they carry, not for whose datasheet is being quoted.
    // Digilent's `uart_rxd_out` / `uart_txd_in` are relative to the BRIDGE, and
    // reading them as relative to the host is equally grammatical -- an ambiguity
    // that cost several hardware cycles here. Direction is now in the name.
    //
    // Which package pin is which was MEASURED, not inferred: with the host
    // transmitting continuously, J17 showed edges and J18 was static
    // (fpga/rtl/pinprobe.v, 2026-08-22). The FPGA therefore receives on J17.
    input  wire uart_rx_from_host,   // J17
    output wire uart_tx_to_host,     // J18
    output wire [1:0] led
);
    reg rst = 1'b1;
    reg [7:0] rst_cnt = 8'd0;
    always @(posedge clk) begin
        if (rst_cnt != 8'hFF) begin rst_cnt <= rst_cnt + 8'd1; rst <= 1'b1; end
        else rst <= 1'b0;
    end

    wire [7:0] rx_data;
    wire       rx_valid;
    reg  [7:0] tx_data;
    reg        tx_send;
    wire       tx_busy;

    uart_rx #(.CLK_HZ(CLK_HZ), .BAUD(BAUD)) urx
        (.clk(clk), .rst(rst), .rx(uart_rx_from_host), .data(rx_data), .valid(rx_valid));
    uart_tx #(.CLK_HZ(CLK_HZ), .BAUD(BAUD)) utx
        (.clk(clk), .rst(rst), .data(tx_data), .send(tx_send),
         .tx(uart_tx_to_host), .busy(tx_busy));

    // ---- command reception -------------------------------------------------
    localparam integer WORK_BYTES = 48;
    reg [7:0]  work [0:WORK_BYTES-1];
    reg [5:0]  work_idx;
    reg        loading;
    reg        start_scan;

    integer k;
    reg [255:0] midstate;
    reg [95:0]  tail;
    reg [31:0]  nonce_start;

    always @(posedge clk) begin
        start_scan <= 1'b0;
        if (rst) begin
            loading <= 1'b0; work_idx <= 6'd0;
        end else if (rx_valid) begin
            if (loading) begin
                work[work_idx] <= rx_data;
                if (work_idx == WORK_BYTES-1) begin
                    loading    <= 1'b0;
                    start_scan <= 1'b1;
                end else begin
                    work_idx <= work_idx + 6'd1;
                end
            end else begin
                case (rx_data)
                    8'h57: begin loading <= 1'b1; work_idx <= 6'd0; end   // 'W'
                    default: ;                                            // 'S'/'P' below
                endcase
            end
        end
    end

    // assemble the work registers combinationally at start
    always @(posedge clk) begin
        if (start_scan) begin
            for (k = 0; k < 32; k = k + 1)
                midstate[255 - 8*k -: 8] <= work[k];
            for (k = 0; k < 12; k = k + 1)
                tail[95 - 8*k -: 8] <= work[32 + k];
            nonce_start <= {work[44], work[45], work[46], work[47]};
        end
    end

    reg scan_go;
    always @(posedge clk) scan_go <= start_scan;   // one cycle after registers land

    // ---- the scanner -------------------------------------------------------
    wire         busy, found, exhausted;
    wire [31:0]  golden_nonce;
    wire [255:0] golden_hash;
    wire         abort = rx_valid && (rx_data == 8'h53) && !loading;

    sha256d_miner #(.ZERO_WORDS(ZERO_WORDS)) miner (
        .clk(clk), .rst(rst | abort), .start(scan_go),
        .midstate(midstate), .tail(tail),
        .nonce_start(nonce_start), .nonce_count(32'd0),
        .busy(busy), .found(found), .golden_nonce(golden_nonce),
        .golden_hash(golden_hash), .exhausted(exhausted)
    );

    // ---- reporting ---------------------------------------------------------
    // A found result is latched and shifted out as 1 + 4 + 32 = 37 bytes.
    reg [295:0] report;         // {0x46, nonce, digest}
    reg [5:0]   rep_left;
    reg         ping_pending;

    always @(posedge clk) begin
        tx_send <= 1'b0;
        if (rst) begin
            rep_left <= 6'd0; ping_pending <= 1'b0;
        end else begin
            if (rx_valid && !loading && rx_data == 8'h50) ping_pending <= 1'b1;   // 'P'

            if (found && rep_left == 0) begin
                report   <= {8'h46, golden_nonce, golden_hash};
                rep_left <= 6'd37;
            end else if (exhausted && rep_left == 0) begin
                report   <= {8'h45, 288'd0};
                rep_left <= 6'd1;
            end else if (rep_left != 0 && !tx_busy && !tx_send) begin
                tx_data  <= report[295 -: 8];
                report   <= {report[287:0], 8'h00};
                tx_send  <= 1'b1;
                rep_left <= rep_left - 6'd1;
            end else if (ping_pending && rep_left == 0 && !tx_busy && !tx_send) begin
                tx_data      <= 8'h4B;                                            // 'K'
                tx_send      <= 1'b1;
                ping_pending <= 1'b0;
            end
        end
    end

    // ---- heartbeat ---------------------------------------------------------
    // LED0 blinks at 1 Hz off the input clock alone, independent of the UART,
    // the reset counter and the miner. Without it an unprogrammed board and a
    // board whose serial link is broken look identical -- both LEDs dark -- and
    // bring-up cannot tell "no bitstream" from "no link". It doubles as a
    // measurement of CLK_HZ: a blink that is visibly not 1 Hz means the
    // parameter disagrees with the crystal, which is the same error that
    // silently corrupts the baud divisor and makes the UART emit garbage.
    localparam integer HALF_SECOND = CLK_HZ / 2;
    reg [31:0] hb_cnt    = 32'd0;
    reg        heartbeat = 1'b0;
    always @(posedge clk) begin
        if (hb_cnt >= HALF_SECOND - 1) begin
            hb_cnt    <= 32'd0;
            heartbeat <= ~heartbeat;
        end else begin
            hb_cnt <= hb_cnt + 32'd1;
        end
    end

    assign led = {busy, heartbeat};
endmodule
`default_nettype wire
