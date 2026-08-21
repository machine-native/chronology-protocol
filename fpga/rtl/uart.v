// Minimal 8N1 UART transmitter and receiver.
//
// Kept separate and trivially small so it can be reasoned about at a glance: the
// miner's correctness must never depend on subtle serial behaviour. Oversampling
// on receive is the usual mid-bit sample; transmit is a plain shift register.
`default_nettype none

module uart_tx #(
    parameter integer CLK_HZ  = 100_000_000,
    parameter integer BAUD    = 115200
) (
    input  wire       clk,
    input  wire       rst,
    input  wire [7:0] data,
    input  wire       send,        // pulse; ignored while busy
    output reg        tx,
    output reg        busy
);
    localparam integer DIV = CLK_HZ / BAUD;
    reg [15:0] cnt;
    reg [3:0]  bit_idx;
    reg [9:0]  shifter;            // {stop, data[7:0], start}

    always @(posedge clk) begin
        if (rst) begin
            tx <= 1'b1; busy <= 1'b0; cnt <= 0; bit_idx <= 0;
        end else if (!busy) begin
            tx <= 1'b1;
            if (send) begin
                shifter <= {1'b1, data, 1'b0};
                busy    <= 1'b1;
                cnt     <= 0;
                bit_idx <= 0;
            end
        end else begin
            if (cnt == DIV - 1) begin
                cnt <= 0;
                tx  <= shifter[bit_idx];
                if (bit_idx == 4'd9) busy <= 1'b0;
                else                 bit_idx <= bit_idx + 4'd1;
            end else begin
                cnt <= cnt + 16'd1;
            end
        end
    end
endmodule


module uart_rx #(
    parameter integer CLK_HZ = 100_000_000,
    parameter integer BAUD   = 115200
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       rx,
    output reg  [7:0] data,
    output reg        valid        // 1-cycle pulse
);
    localparam integer DIV = CLK_HZ / BAUD;
    reg [15:0] cnt;
    reg [3:0]  bit_idx;
    reg        busy;
    reg [1:0]  sync;               // two-flop synchroniser for the async input

    always @(posedge clk) begin
        sync <= {sync[0], rx};
        if (rst) begin
            busy <= 1'b0; valid <= 1'b0; cnt <= 0; bit_idx <= 0;
        end else begin
            valid <= 1'b0;
            if (!busy) begin
                if (sync[1] == 1'b0) begin        // start bit edge
                    busy    <= 1'b1;
                    cnt     <= DIV / 2;           // sample mid-bit
                    bit_idx <= 0;
                end
            end else begin
                if (cnt == DIV - 1) begin
                    cnt <= 0;
                    // bit_idx 0 is the START bit and must be discarded, not stored.
                    // (Storing it shifts every byte by one position — the first
                    // version of this module did exactly that and no byte ever
                    // arrived intact.) 1..8 are data bits 0..7; 9 is the stop bit.
                    if (bit_idx == 4'd0) begin
                        bit_idx <= 4'd1;
                    end else if (bit_idx <= 4'd8) begin
                        data    <= {sync[1], data[7:1]};
                        bit_idx <= bit_idx + 4'd1;
                    end else begin
                        busy  <= 1'b0;
                        valid <= 1'b1;
                    end
                end else begin
                    cnt <= cnt + 16'd1;
                end
            end
        end
    end
endmodule
`default_nettype wire
