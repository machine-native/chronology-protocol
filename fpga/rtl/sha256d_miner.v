// SHA-256d nonce scanner for the anchor chain.
//
// Work is handed over already partly digested by the host, which is both faster
// and safer: the host compresses the header's first 64 bytes (fixed for a given
// template) into `midstate`, and sends only the 12-byte tail — merkle tail, nTime,
// nBits — that precedes the nonce. Per nonce the hardware then does exactly two
// compressions:
//
//   pass A: midstate + {tail, nonce, padding}      -> first SHA-256
//   pass B: IV       + {first hash, padding}       -> second SHA-256
//
// A found candidate is reported when the LAST `ZERO_WORDS` words of the digest
// are zero. Byte order matters and is easy to get backwards: the digest is
// {H0..H7} with H0 first, while a block hash is *displayed* byte-reversed. So the
// leading zeros everyone looks for in `00000000fc80fe4f...` are the trailing
// words of the raw digest — H7, then H6 — not H0.
//
// DELIBERATE DESIGN CHOICE: this is a COARSE filter, not the consensus rule. The
// host re-checks every reported nonce against the exact compact target using the
// already-tested software path. Hardware narrows the search; software decides what
// is valid. A bug here can waste effort or miss a candidate, but it cannot cause
// an invalid block to be claimed valid.
`default_nettype none

module sha256d_miner #(
    parameter integer ZERO_WORDS   = 1,     // 1 -> ~2^32 filter, matches difficulty-1
    // Nonce increment. With N cores each given a stride of N and a start offset
    // of its own index, the cores interleave: together they cover every nonce
    // exactly once, with no overlap and no coordination. Contiguous slicing
    // would work too, but then reaching an answer D nonces away is one core's
    // job and the other N-1 grind through unrelated ranges -- which makes a
    // benchmark measure a single core while looking like it measures the array.
    parameter integer NONCE_STRIDE = 1
) (
    input  wire         clk,
    input  wire         rst,
    input  wire         start,             // pulse to begin scanning
    input  wire [255:0] midstate,          // host-computed, over header[0:64]
    input  wire [95:0]  tail,              // header[64:76] : merkle tail, nTime, nBits
    input  wire [31:0]  nonce_start,
    input  wire [31:0]  nonce_count,       // 0 => run to 2^32 wrap
    output reg          busy,
    output reg          found,             // 1-cycle pulse with golden_nonce valid
    output reg  [31:0]  golden_nonce,
    output reg  [255:0] golden_hash,
    output reg          exhausted          // 1-cycle pulse: range finished, nothing found
);
    localparam [255:0] IV =
        256'h6a09e667_bb67ae85_3c6ef372_a54ff53a_510e527f_9b05688c_1f83d9ab_5be0cd19;

    // The nonce is a NUMBER here but is stored little-endian in the header, so it
    // must be byte-swapped on the way into the block. (Getting this wrong makes the
    // scanner silently find nothing, which is exactly how it first behaved.)
    function [31:0] bswap32(input [31:0] x);
        bswap32 = { x[7:0], x[15:8], x[23:16], x[31:24] };
    endfunction
    // The 80-byte header is 640 bits; block 2 carries 16 data bytes then padding.
    function [511:0] block2(input [95:0] t, input [31:0] n);
        block2 = { t, bswap32(n), 8'h80, 312'd0, 64'd640 };
    endfunction
    // The outer hash digests 32 bytes -> 256-bit length field.
    function [511:0] block3(input [255:0] d);
        block3 = { d, 8'h80, 184'd0, 64'd256 };
    endfunction

    reg  [31:0]  nonce, remaining;
    reg          unlimited;
    reg  [1:0]   phase;                    // 0 idle, 1 pass A, 2 pass B
    reg          core_start;
    reg  [255:0] core_state_in;
    reg  [511:0] core_block_in;
    wire         core_done;
    wire [255:0] core_state_out;

    sha256_core core (
        .clk(clk), .rst(rst), .start(core_start),
        .state_in(core_state_in), .block_in(core_block_in),
        .done(core_done), .state_out(core_state_out)
    );

    wire hit = (core_state_out[32*ZERO_WORDS-1 : 0] == {(32*ZERO_WORDS){1'b0}});

    always @(posedge clk) begin
        if (rst) begin
            busy <= 1'b0; found <= 1'b0; exhausted <= 1'b0;
            phase <= 2'd0; core_start <= 1'b0;
        end else begin
            found      <= 1'b0;
            exhausted  <= 1'b0;
            core_start <= 1'b0;

            if (start && !busy) begin
                busy      <= 1'b1;
                nonce     <= nonce_start;
                remaining <= nonce_count;
                unlimited <= (nonce_count == 32'd0);
                phase     <= 2'd1;
                core_state_in <= midstate;
                core_block_in <= block2(tail, nonce_start);
                core_start    <= 1'b1;
            end else if (busy && core_done) begin
                if (phase == 2'd1) begin
                    phase         <= 2'd2;
                    core_state_in <= IV;
                    core_block_in <= block3(core_state_out);
                    core_start    <= 1'b1;
                end else begin
                    if (hit) begin
                        found        <= 1'b1;
                        golden_nonce <= nonce;
                        golden_hash  <= core_state_out;
                        busy         <= 1'b0;
                        phase        <= 2'd0;
                    end else if (!unlimited && remaining <= 32'd1) begin
                        exhausted <= 1'b1;
                        busy      <= 1'b0;
                        phase     <= 2'd0;
                    end else begin
                        nonce         <= nonce + NONCE_STRIDE[31:0];
                        remaining     <= remaining - 32'd1;   // nonces done here
                        phase         <= 2'd1;
                        core_state_in <= midstate;
                        core_block_in <= block2(tail, nonce + NONCE_STRIDE[31:0]);
                        core_start    <= 1'b1;
                    end
                end
            end
        end
    end
endmodule
`default_nettype wire
