// End-to-end testbench: bytes in over UART, bytes out over UART.
//
// Feeds the real height-221 work as a host would, and requires the reply to be
// 'F' + the nonce we actually mined + that block's real digest. This exercises the
// command parser, the work registers, the scanner and the reporting path together
// — everything except the physical pins.
//
// Baud/clock are scaled down purely so the simulation finishes quickly; the logic
// is identical.
`timescale 1ns/1ps
`default_nettype none

module tb_miner_top;
    localparam integer CLK_HZ = 1_000_000;
    localparam integer BAUD   = 62_500;
    localparam integer DIV    = CLK_HZ / BAUD;      // 4 cycles/bit

    reg clk = 0;
    reg host_tx = 1'b1;                             // idle high
    wire fpga_tx;
    wire [1:0] led;
    integer fails = 0;

    miner_top #(.CLK_HZ(CLK_HZ), .BAUD(BAUD), .ZERO_WORDS(1)) dut (
        .clk(clk), .uart_rx_from_host(host_tx), .uart_tx_to_host(fpga_tx), .led(led)
    );

    always #500 clk = ~clk;                         // 1 MHz

    // ---- host-side UART ----
    task send_byte(input [7:0] b);
        integer i;
    begin
        host_tx = 1'b0;                             // start
        repeat (DIV) @(posedge clk);
        for (i = 0; i < 8; i = i + 1) begin
            host_tx = b[i];
            repeat (DIV) @(posedge clk);
        end
        host_tx = 1'b1;                             // stop
        repeat (DIV) @(posedge clk);
    end
    endtask

    task recv_byte(output [7:0] b);
        integer i;
    begin
        @(negedge fpga_tx);                         // start bit
        repeat (DIV + DIV/2) @(posedge clk);        // to middle of bit 0
        for (i = 0; i < 8; i = i + 1) begin
            b[i] = fpga_tx;
            repeat (DIV) @(posedge clk);
        end
    end
    endtask

    // height-221 work
    localparam [255:0] MID  =
        256'h5f954a84_7c6313a7_b76d8c90_2295df6a_8610fe0c_fd46289f_1d483e61_5f24dce4;
    localparam [95:0]  TAIL = 96'h04b9b642_c58b856a_ffff001d;
    localparam [31:0]  NONCE = 32'd2757362010;
    localparam [255:0] HASH =
        256'h8b080d36_eef1d5b3_154114bd_5161589f_022f78bf_af9cb527_4ffe80fc_00000000;

    reg [7:0] rb;
    reg [31:0] got_nonce;
    reg [255:0] got_hash;
    integer i;

    initial begin
        repeat (400) @(posedge clk);                // let reset release

        // ping first: the link must answer before we trust anything else
        send_byte(8'h50);
        recv_byte(rb);
        if (rb === 8'h4B) $display("PASS  ping answered 'K'");
        else begin $display("FAIL  ping got %02x", rb); fails = fails + 1; end

        // send work: 'W' + midstate(32) + tail(12) + nonce_start(4)
        send_byte(8'h57);
        for (i = 0; i < 32; i = i + 1) send_byte(MID[255 - 8*i -: 8]);
        for (i = 0; i < 12; i = i + 1) send_byte(TAIL[95 - 8*i -: 8]);
        send_byte((NONCE - 2) >> 24); send_byte((NONCE - 2) >> 16);
        send_byte((NONCE - 2) >> 8);  send_byte((NONCE - 2));

        // expect 'F' + nonce + digest
        recv_byte(rb);
        if (rb !== 8'h46) begin
            $display("FAIL  expected 'F', got %02x", rb);
            fails = fails + 1;
        end else begin
            for (i = 0; i < 4; i = i + 1)  begin recv_byte(rb); got_nonce = {got_nonce[23:0], rb}; end
            for (i = 0; i < 32; i = i + 1) begin recv_byte(rb); got_hash  = {got_hash[247:0], rb}; end
            if (got_nonce === NONCE) $display("PASS  reported nonce %0d over UART", got_nonce);
            else begin $display("FAIL  nonce %0d, expected %0d", got_nonce, NONCE); fails = fails + 1; end
            if (got_hash === HASH) $display("PASS  reported the chain's own digest");
            else begin
                $display("FAIL  digest mismatch");
                $display("        got %064x", got_hash);
                $display("        exp %064x", HASH);
                fails = fails + 1;
            end
        end

        if (fails == 0) $display("\nTOP-LEVEL OK — real work in, real answer out, over UART");
        else            $display("\n%0d FAILURE(S)", fails);
        $finish;
    end

    initial begin
        #500_000_000;
        $display("TIMEOUT");
        $finish;
    end
endmodule
`default_nettype wire
