// Testbench for sha256_core.
//
// The vectors are NOT textbook-only. Cases 2-4 are the exact compression steps of
// the header this project mined into height 221 of the live anchor chain, whose
// double-SHA256 is the block hash 00000000fc80fe4f...  If this core is wrong in
// any bit, case 4 cannot produce that value.
`timescale 1ns/1ps
`default_nettype none

module tb_sha256_core;
    reg clk = 0, rst = 1, start = 0;
    reg  [255:0] state_in;
    reg  [511:0] block_in;
    wire         done;
    wire [255:0] state_out;
    integer fails = 0;

    localparam [255:0] IV = 256'h6a09e667_bb67ae85_3c6ef372_a54ff53a_510e527f_9b05688c_1f83d9ab_5be0cd19;

    sha256_core dut (.clk(clk), .rst(rst), .start(start), .state_in(state_in),
                     .block_in(block_in), .done(done), .state_out(state_out));

    always #5 clk = ~clk;

    task run_case;
        input [8*40:1] label;
        input [255:0]  st;
        input [511:0]  blk;
        input [255:0]  exp_val;
    begin
        @(negedge clk);
        state_in = st; block_in = blk; start = 1;
        @(negedge clk); start = 0;
        wait (done);
        @(posedge clk);
        if (state_out === exp_val)
            $display("PASS  %0s", label);
        else begin
            $display("FAIL  %0s", label);
            $display("        got %064x", state_out);
            $display("        exp %064x", exp_val);
            fails = fails + 1;
        end
    end
    endtask

    initial begin
        repeat (4) @(negedge clk);
        rst = 0;

        // 1. FIPS 180-4: SHA-256("abc")
        run_case("FIPS abc", IV,
            512'h61626380_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000018,
            256'hba7816bf_8f01cfea_414140de_5dae2223_b00361a3_96177a9c_b410ff61_f20015ad);

        // 2. midstate of our height-221 header (first 64 bytes)
        run_case("h221 block1 -> midstate", IV,
            512'h01000000_7c6fcea1_66e31419_4c504b99_4e7ce12a_fbe2e02b_622797de_555bcc4c_00000000_bcbe8b1c_d612764d_bbf00203_07af830d_a7dad68e_cea2fbfa_e205b700,
            256'h5f954a84_7c6313a7_b76d8c90_2295df6a_8610fe0c_fd46289f_1d483e61_5f24dce4);

        // 3. second block (tail + nonce 2757362010 + padding) from that midstate
        run_case("h221 block2 -> first hash",
            256'h5f954a84_7c6313a7_b76d8c90_2295df6a_8610fe0c_fd46289f_1d483e61_5f24dce4,
            512'h04b9b642_c58b856a_ffff001d_5a015aa4_80000000_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000280,
            256'hf48062ec_16f5807e_a9751f40_2ba969e7_a010d66c_ac7dbea2_ca94c266_82ed9191);

        // 4. the outer hash — its byte-reverse is the real block hash on the chain
        run_case("h221 final -> chain block hash", IV,
            512'hf48062ec_16f5807e_a9751f40_2ba969e7_a010d66c_ac7dbea2_ca94c266_82ed9191_80000000_00000000_00000000_00000000_00000000_00000000_00000000_00000100,
            256'h8b080d36_eef1d5b3_154114bd_5161589f_022f78bf_af9cb527_4ffe80fc_00000000);

        // 5. back-to-back issue: the core must be reusable immediately
        run_case("reuse after completion", IV,
            512'h61626380_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000000_00000018,
            256'hba7816bf_8f01cfea_414140de_5dae2223_b00361a3_96177a9c_b410ff61_f20015ad);

        if (fails == 0) $display("\nALL VECTORS PASS");
        else            $display("\n%0d FAILURE(S)", fails);
        $finish;
    end

    initial begin
        #200000;
        $display("TIMEOUT");
        $finish;
    end
endmodule
`default_nettype wire
