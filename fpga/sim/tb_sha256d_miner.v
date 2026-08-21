// Testbench for sha256d_miner.
//
// The decisive test: hand the scanner the real work for height 221 of the anchor
// chain, with a nonce range that brackets the nonce we actually mined, and require
// it to find that exact nonce and that exact hash. Nothing about this is synthetic
// — the answer was established by real proof-of-work on a live chain in 2026.
`timescale 1ns/1ps
`default_nettype none

module tb_sha256d_miner;
    reg clk = 0, rst = 1, start = 0;
    reg  [255:0] midstate;
    reg  [95:0]  tail;
    reg  [31:0]  nonce_start, nonce_count;
    wire         busy, found, exhausted;
    wire [31:0]  golden_nonce;
    wire [255:0] golden_hash;
    integer fails = 0;

    // height 221: midstate over header[0:64], tail = header[64:76]
    localparam [255:0] MID_221 =
        256'h5f954a84_7c6313a7_b76d8c90_2295df6a_8610fe0c_fd46289f_1d483e61_5f24dce4;
    localparam [95:0]  TAIL_221 = 96'h04b9b642_c58b856a_ffff001d;
    localparam [31:0]  NONCE_221 = 32'd2757362010;
    localparam [255:0] HASH_221 =
        256'h8b080d36_eef1d5b3_154114bd_5161589f_022f78bf_af9cb527_4ffe80fc_00000000;

    sha256d_miner #(.ZERO_WORDS(1)) dut (
        .clk(clk), .rst(rst), .start(start), .midstate(midstate), .tail(tail),
        .nonce_start(nonce_start), .nonce_count(nonce_count),
        .busy(busy), .found(found), .golden_nonce(golden_nonce),
        .golden_hash(golden_hash), .exhausted(exhausted)
    );

    always #5 clk = ~clk;

    task expect_found;
        input [31:0] want_nonce;
        input [255:0] want_hash;
    begin
        wait (found || exhausted);
        @(posedge clk);
        if (exhausted) begin
            $display("FAIL  range exhausted, expected a hit at nonce %0d", want_nonce);
            fails = fails + 1;
        end else if (golden_nonce !== want_nonce) begin
            $display("FAIL  found nonce %0d, expected %0d", golden_nonce, want_nonce);
            fails = fails + 1;
        end else if (golden_hash !== want_hash) begin
            $display("FAIL  hash mismatch at nonce %0d", want_nonce);
            $display("        got %064x", golden_hash);
            $display("        exp %064x", want_hash);
            fails = fails + 1;
        end else begin
            $display("PASS  found real nonce %0d with the chain's own hash", golden_nonce);
        end
    end
    endtask

    initial begin
        repeat (4) @(negedge clk);
        rst = 0;
        @(negedge clk);

        // 1. scan a window that brackets the real nonce; must land exactly on it
        midstate = MID_221; tail = TAIL_221;
        nonce_start = NONCE_221 - 32'd3; nonce_count = 32'd10;
        start = 1; @(negedge clk); start = 0;
        expect_found(NONCE_221, HASH_221);

        // 2. a window that stops just short must report exhaustion, not a false hit
        @(negedge clk);
        nonce_start = NONCE_221 - 32'd5; nonce_count = 32'd4;
        start = 1; @(negedge clk); start = 0;
        wait (found || exhausted);
        @(posedge clk);
        if (exhausted && !found)
            $display("PASS  short range exhausted cleanly, no false positive");
        else begin
            $display("FAIL  short range should have exhausted without a hit");
            fails = fails + 1;
        end

        // 3. starting exactly on the winning nonce must hit on the first try
        @(negedge clk);
        nonce_start = NONCE_221; nonce_count = 32'd1;
        start = 1; @(negedge clk); start = 0;
        expect_found(NONCE_221, HASH_221);

        if (fails == 0) $display("\nMINER OK — reproduced real proof-of-work from the chain");
        else            $display("\n%0d FAILURE(S)", fails);
        $finish;
    end

    initial begin
        #5000000;
        $display("TIMEOUT");
        $finish;
    end
endmodule
`default_nettype wire
