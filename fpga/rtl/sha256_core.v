// SHA-256 compression core — one round per cycle, 64 cycles per 512-bit block.
//
// Deliberately the simple shape first: correctness is established against
// known-answer vectors (including headers this project actually mined) before
// any unrolling or pipelining is attempted. Throughput work comes after the
// testbench is green, never before.
//
// Interface: load `state_in` (the chaining value / midstate) and `block_in`
// (512 bits, big-endian words), raise `start`, wait for `done`; `state_out`
// then holds state_in + compressed block, per FIPS 180-4.
`default_nettype none

module sha256_core (
    input  wire         clk,
    input  wire         rst,
    input  wire         start,
    input  wire [255:0] state_in,     // {H0,...,H7}, H0 in the MSBs
    input  wire [511:0] block_in,     // W0..W15, W0 in the MSBs
    output reg          done,
    output reg  [255:0] state_out
);
    function [31:0] rotr(input [31:0] x, input integer n);
        rotr = (x >> n) | (x << (32 - n));
    endfunction
    function [31:0] ssig0(input [31:0] x);
        ssig0 = rotr(x, 7) ^ rotr(x, 18) ^ (x >> 3);
    endfunction
    function [31:0] ssig1(input [31:0] x);
        ssig1 = rotr(x, 17) ^ rotr(x, 19) ^ (x >> 10);
    endfunction
    function [31:0] bsig0(input [31:0] x);
        bsig0 = rotr(x, 2) ^ rotr(x, 13) ^ rotr(x, 22);
    endfunction
    function [31:0] bsig1(input [31:0] x);
        bsig1 = rotr(x, 6) ^ rotr(x, 11) ^ rotr(x, 25);
    endfunction

    reg [31:0] K [0:63];
    initial begin
        K[ 0]=32'h428a2f98; K[ 1]=32'h71374491; K[ 2]=32'hb5c0fbcf; K[ 3]=32'he9b5dba5;
        K[ 4]=32'h3956c25b; K[ 5]=32'h59f111f1; K[ 6]=32'h923f82a4; K[ 7]=32'hab1c5ed5;
        K[ 8]=32'hd807aa98; K[ 9]=32'h12835b01; K[10]=32'h243185be; K[11]=32'h550c7dc3;
        K[12]=32'h72be5d74; K[13]=32'h80deb1fe; K[14]=32'h9bdc06a7; K[15]=32'hc19bf174;
        K[16]=32'he49b69c1; K[17]=32'hefbe4786; K[18]=32'h0fc19dc6; K[19]=32'h240ca1cc;
        K[20]=32'h2de92c6f; K[21]=32'h4a7484aa; K[22]=32'h5cb0a9dc; K[23]=32'h76f988da;
        K[24]=32'h983e5152; K[25]=32'ha831c66d; K[26]=32'hb00327c8; K[27]=32'hbf597fc7;
        K[28]=32'hc6e00bf3; K[29]=32'hd5a79147; K[30]=32'h06ca6351; K[31]=32'h14292967;
        K[32]=32'h27b70a85; K[33]=32'h2e1b2138; K[34]=32'h4d2c6dfc; K[35]=32'h53380d13;
        K[36]=32'h650a7354; K[37]=32'h766a0abb; K[38]=32'h81c2c92e; K[39]=32'h92722c85;
        K[40]=32'ha2bfe8a1; K[41]=32'ha81a664b; K[42]=32'hc24b8b70; K[43]=32'hc76c51a3;
        K[44]=32'hd192e819; K[45]=32'hd6990624; K[46]=32'hf40e3585; K[47]=32'h106aa070;
        K[48]=32'h19a4c116; K[49]=32'h1e376c08; K[50]=32'h2748774c; K[51]=32'h34b0bcb5;
        K[52]=32'h391c0cb3; K[53]=32'h4ed8aa4a; K[54]=32'h5b9cca4f; K[55]=32'h682e6ff3;
        K[56]=32'h748f82ee; K[57]=32'h78a5636f; K[58]=32'h84c87814; K[59]=32'h8cc70208;
        K[60]=32'h90befffa; K[61]=32'ha4506ceb; K[62]=32'hbef9a3f7; K[63]=32'hc67178f2;
    end

    reg [31:0] a,b,c,d,e,f,g,h;
    reg [31:0] h0,h1,h2,h3,h4,h5,h6,h7;
    reg [31:0] w [0:15];              // rolling 16-word window
    reg [6:0]  round;
    reg        busy;

    wire [31:0] wt = w[0];
    wire [31:0] w_next = ssig1(w[14]) + w[9] + ssig0(w[1]) + w[0];
    wire [31:0] t1 = h + bsig1(e) + ((e & f) ^ (~e & g)) + K[round[5:0]] + wt;
    wire [31:0] t2 = bsig0(a) + ((a & b) ^ (a & c) ^ (b & c));

    integer i;
    always @(posedge clk) begin
        if (rst) begin
            busy <= 1'b0; done <= 1'b0; round <= 7'd0;
        end else begin
            done <= 1'b0;
            if (start && !busy) begin
                busy  <= 1'b1;
                round <= 7'd0;
                {h0,h1,h2,h3,h4,h5,h6,h7} <= state_in;
                {a,b,c,d,e,f,g,h}         <= state_in;
                for (i = 0; i < 16; i = i + 1)
                    w[i] <= block_in[511 - 32*i -: 32];
            end else if (busy) begin
                // round function
                h <= g; g <= f; f <= e; e <= d + t1;
                d <= c; c <= b; b <= a; a <= t1 + t2;
                // message schedule slides; new word appears at w[15]
                for (i = 0; i < 15; i = i + 1)
                    w[i] <= w[i+1];
                w[15] <= w_next;

                if (round == 7'd63) begin
                    busy  <= 1'b0;
                    done  <= 1'b1;
                    state_out <= { h0 + (t1 + t2), h1 + a, h2 + b, h3 + c,
                                   h4 + (d + t1), h5 + e, h6 + f, h7 + g };
                end
                round <= round + 7'd1;
            end
        end
    end
endmodule
`default_nettype wire
