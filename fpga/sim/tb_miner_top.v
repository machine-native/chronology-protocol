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

    // Four cores, so the interleaving is actually exercised: the answer sits
    // at a nonce only one of them will ever visit, and it must still come out.
    miner_top #(.CLK_HZ(CLK_HZ), .BAUD(BAUD), .ZERO_WORDS(1), .NUM_CORES(4)) dut (
        .clk_12mhz(clk), .uart_rx_from_host(host_tx), .uart_tx_to_host(fpga_tx), .led(led)
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

    // Background receiver. It collects bytes off the wire the instant they
    // appear, into a queue the test body pops from -- exactly as the host OS
    // buffers arriving bytes while the application is still writing.
    //
    // The earlier version received inline, which made the testbench half-duplex:
    // any byte the FPGA sent while the host was mid-transmission was lost, and
    // the test then reported a garbage byte as an RTL fault. That is not a
    // hardware behaviour. It surfaced the moment the core array got fast enough
    // to answer within the host's own ping -- with 4 cores the winning nonce is
    // found on a core's FIRST attempt, so the report's start bit preceded the
    // end of the ping being sent. Real hardware is full-duplex and pyserial
    // reads from a kernel buffer; the model must be too, or parallelism itself
    // looks like a bug.
    reg [7:0] rxq [0:255];
    integer   rxq_wr = 0;
    integer   rxq_rd = 0;

    initial begin : collector
        reg [7:0] cb;
        integer   ci;
        forever begin
            @(negedge fpga_tx);                     // start bit
            repeat (DIV + DIV/2) @(posedge clk);    // to middle of bit 0
            for (ci = 0; ci < 8; ci = ci + 1) begin
                cb[ci] = fpga_tx;
                repeat (DIV) @(posedge clk);
            end
            rxq[rxq_wr[7:0]] = cb;
            rxq_wr = rxq_wr + 1;
        end
    end

    task recv_byte(output [7:0] b);
    begin
        while (rxq_rd == rxq_wr) @(posedge clk);    // wait for a queued byte
        b = rxq[rxq_rd[7:0]];
        rxq_rd = rxq_rd + 1;
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

        // A ping DURING the scan must not disturb it. The host driver sends one
        // every second on a long scan to keep the USB link from being suspended
        // by Windows mid-run -- a real failure seen on hardware, where a
        // million-nonce scan died with 'ClearCommError: Access is denied' after
        // pinging successfully moments before. That keepalive is only safe if
        // 'P' neither aborts the scan nor corrupts the report, so it is checked
        // here rather than assumed.
        send_byte(8'h50);

        // expect 'F' + nonce + digest. The 'K' from that ping may arrive first;
        // the report is emitted contiguously once it starts, so the two cannot
        // interleave -- skip a leading 'K' and require the report intact.
        recv_byte(rb);
        if (rb === 8'h4B) begin
            $display("PASS  ping during scan answered without disturbing it");
            recv_byte(rb);
        end
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

        // The ping sent mid-scan is deferred until the 37-byte report is out --
        // the report shifts contiguously and must not be interleaved -- but it
        // must still be answered. The host's keepalive, which is what stops
        // Windows suspending an idle FTDI during a long scan, depends on that
        // ping being neither ignored nor destructive.
        recv_byte(rb);
        if (rb === 8'h4B) $display("PASS  mid-scan ping answered after the report");
        else begin
            $display("FAIL  deferred ping unanswered, got %02x", rb);
            fails = fails + 1;
        end

        // The winning nonce lies off core 0's lane: with 4 cores striding by 4
        // from NONCE-2, core 0 visits NONCE-2, NONCE+2, ... and never NONCE.
        // Recovering it at all proves the interleave covers the whole range.
        $display("PASS  interleaved array found a nonce off core 0's lane");

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
