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
    // Frequency the LOGIC runs at, synthesised by the MMCM from the board's
    // 12 MHz oscillator. Drives the baud divisor and the heartbeat, so it must
    // match what the MMCM actually produces -- both are derived from it below,
    // so there is one knob and no way for them to disagree.
    parameter integer CLK_HZ     = 60_000_000,
    parameter integer BAUD       = 115200,
    parameter integer ZERO_WORDS = 1,
    // Parallel scanners. Each is given stride NUM_CORES and start offset equal
    // to its own index, so together they cover every nonce exactly once.
    parameter integer NUM_CORES  = 8
) (
    input  wire clk_12mhz,
    // Named for what they carry, not for whose datasheet is being quoted.
    // Digilent's `uart_rxd_out` / `uart_txd_in` are relative to the HOST side,
    // and reading them as bridge-relative is equally grammatical -- an ambiguity
    // that cost several hardware cycles here. Direction is now in the name.
    //
    // Which pin carries what was MEASURED, not inferred: with the host
    // transmitting continuously, J17 showed edges and J18 was static
    // (fpga/rtl/pinprobe.v, 2026-08-22). The FPGA therefore receives on J17.
    //
    // The original bug was the DIRECTIONS, not the pin numbers -- those matched
    // Digilent's master XDC exactly. Their names are relative to the host, so
    // `uart_txd_in` is data the host transmits INTO the board: an FPGA input.
    // It had been declared an output, which drove J17 against the FT2232.
    input  wire uart_rx_from_host,   // J17
    output wire uart_tx_to_host,     // J18
    output wire [1:0] led
);
    // ---- clocking ----------------------------------------------------------
    // The board oscillator is 12 MHz, which caps the array at 0.09 MH/s no
    // matter how many cores are instanced. An MMCM multiplies it up: VCO is
    // fixed at 600 MHz (12 x 50, inside the -1 part's 600-1200 MHz range) and
    // CLKOUT0 divides that down to CLK_HZ. One parameter therefore sets the
    // clock, the baud divisor and the heartbeat period together.
    //
    // MMCME2_BASE is a Xilinx primitive that Icarus cannot elaborate, so
    // simulation bypasses it and runs the logic straight off the input clock.
    // The RTL below is identical either way; only the timebase changes.
    localparam real MMCM_VCO_MHZ = 600.0;
    localparam real CLKOUT_DIV   = MMCM_VCO_MHZ / (CLK_HZ / 1000000.0);

    wire clk;
    wire mmcm_locked;
`ifdef NO_MMCM
    assign clk         = clk_12mhz;
    assign mmcm_locked = 1'b1;
`else
    wire clk_raw, clk_fb;
    MMCME2_BASE #(
        .CLKIN1_PERIOD   (83.333),          // 12 MHz
        .DIVCLK_DIVIDE   (1),
        .CLKFBOUT_MULT_F (50.0),            // -> 600 MHz VCO
        .CLKOUT0_DIVIDE_F(CLKOUT_DIV),
        .BANDWIDTH       ("OPTIMIZED")
    ) mmcm (
        .CLKIN1(clk_12mhz), .CLKFBIN(clk_fb), .CLKFBOUT(clk_fb),
        .CLKOUT0(clk_raw),  .LOCKED(mmcm_locked),
        .RST(1'b0), .PWRDWN(1'b0)
    );
    BUFG bufg_sys (.I(clk_raw), .O(clk));
`endif

    // Reset is held until the MMCM locks. Running logic on an unlocked clock
    // means running on a frequency that is still moving, which is a good way to
    // corrupt state that then looks like a logic bug.
    reg rst = 1'b1;
    reg [7:0] rst_cnt = 8'd0;
    always @(posedge clk) begin
        if (!mmcm_locked) begin
            rst_cnt <= 8'd0; rst <= 1'b1;
        end else if (rst_cnt != 8'hFF) begin
            rst_cnt <= rst_cnt + 8'd1; rst <= 1'b1;
        end else begin
            rst <= 1'b0;
        end
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

    // ---- the scanner array -------------------------------------------------
    // NUM_CORES independent scanners, interleaved: core i starts at
    // nonce_start + i and steps by NUM_CORES. Between them they cover every
    // nonce exactly once, in order, with no shared state and no arbitration
    // during the search -- each core simply never looks at another's nonces.
    //
    // Interleaving rather than slicing the range into contiguous blocks is
    // deliberate. With slicing, an answer D nonces ahead is found by one core
    // while the rest grind through unrelated regions, so wall-clock tracks a
    // SINGLE core's rate while appearing to measure the array. Interleaved, the
    // array reaches a target D nonces away in D/(N x per-core rate), which is
    // what "aggregate throughput" should mean.
    wire abort = rx_valid && (rx_data == 8'h53) && !loading;

    wire [NUM_CORES-1:0]     c_busy, c_found, c_exhausted;
    wire [32*NUM_CORES-1:0]  c_nonce;
    wire [256*NUM_CORES-1:0] c_hash;

    genvar g;
    generate
        for (g = 0; g < NUM_CORES; g = g + 1) begin : core_array
            sha256d_miner #(
                .ZERO_WORDS  (ZERO_WORDS),
                .NONCE_STRIDE(NUM_CORES)
            ) miner (
                .clk(clk), .rst(rst | abort), .start(scan_go),
                .midstate(midstate), .tail(tail),
                .nonce_start(nonce_start + g[31:0]),
                .nonce_count(32'd0),
                .busy        (c_busy[g]),
                .found       (c_found[g]),
                .golden_nonce(c_nonce[32*g  +: 32]),
                .golden_hash (c_hash [256*g +: 256]),
                .exhausted   (c_exhausted[g])
            );
        end
    endgenerate

    wire busy = |c_busy;

    // Winner selection. Two cores can report in the same cycle -- they scan
    // disjoint nonces, so both would be genuine candidates -- and only one
    // report can be shifted out. Scanning downwards makes the lowest index win,
    // which is arbitrary but deterministic; the loser's nonce is simply dropped.
    // That costs nothing real: the host re-checks any reported nonce against
    // the exact target anyway, and a missed candidate at difficulty 1 is a
    // retry, not a lost block.
    integer ci;
    reg          found;
    reg [31:0]   golden_nonce;
    reg [255:0]  golden_hash;
    always @(*) begin
        found        = 1'b0;
        golden_nonce = 32'd0;
        golden_hash  = 256'd0;
        for (ci = NUM_CORES-1; ci >= 0; ci = ci - 1) begin
            if (c_found[ci]) begin
                found        = 1'b1;
                golden_nonce = c_nonce[32*ci  +: 32];
                golden_hash  = c_hash [256*ci +: 256];
            end
        end
    end

    // Exhaustion is a one-cycle pulse per core and the cores finish at
    // different times, so each is latched and the array reports exhausted only
    // once every core has. (With nonce_count = 0 the cores run to the 2^32 wrap
    // and this never fires; it is kept correct for when a bounded range is used.)
    reg [NUM_CORES-1:0] exh_latch;
    reg                 all_exh_d;
    wire                all_exh = &exh_latch;
    always @(posedge clk) begin
        if (rst || abort || scan_go) begin
            exh_latch <= {NUM_CORES{1'b0}};
            all_exh_d <= 1'b0;
        end else begin
            exh_latch <= exh_latch | c_exhausted;
            all_exh_d <= all_exh;
        end
    end
    wire exhausted = all_exh && !all_exh_d;   // rising edge -> one pulse

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
