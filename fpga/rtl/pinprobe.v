// Pin-direction probe for the Cmod A7 USB-UART bridge. Not part of the miner.
//
// WHY THIS EXISTS
//
// The miner's bitstream loads, meets timing, and blinks its heartbeat, yet the
// serial link is silent in BOTH directions. That pattern is what a swapped
// transmit/receive pin looks like, and the pin naming does not settle the
// question: Digilent labels the two nets `uart_rxd_out` and `uart_txd_in`, which
// can be read as relative to the BRIDGE (making `uart_rxd_out` an FPGA input) or
// relative to the HOST (making it an FPGA output). Both readings are grammatical.
// Guessing has already cost two rebuilds.
//
// So ask the board instead of arguing about the datasheet.
//
// HOW IT WORKS
//
// Both pins are declared as INPUTS -- the FPGA never drives either one, so there
// is no possibility of two drivers fighting on a line, which is why this is safe
// to run before knowing the answer. Each pin gets a weak internal PULLDOWN.
//
//   - The pin the bridge TRANSMITS on is actively driven high while idle (UART
//     lines idle high). A strong driver beats a weak pulldown: reads 1.
//   - The pin the bridge RECEIVES on is an input on its side, so nothing drives
//     it. The pulldown wins: reads 0.
//
// The pin that reads 1 is the bridge's output, and therefore the FPGA's RX.
//
// READING THE RESULT
//
// Each LED always blinks, so a dark board still means "no bitstream" and can
// never be confused with a pin reading low:
//
//   FAST flicker (~3 Hz) = that pin is HIGH = bridge drives it = FPGA's RX
//   SLOW blink   (~0.7 Hz) = that pin is LOW  = nothing drives it = FPGA's TX
//
//   LD1 = uart_rxd_out (J18)      LD2 = uart_txd_in (J17)
//
//   LD1 fast, LD2 slow  -> the miner's current declaration is CORRECT
//   LD1 slow, LD2 fast  -> the pins are SWAPPED; that is the bug
//   both slow           -> the bridge drives neither: the UART channel is not
//                          active, so COM4 is not this board's serial channel
//   both fast           -> inconclusive; report it and do not proceed
`default_nettype none

module pinprobe (
    input  wire clk,
    input  wire uart_rxd_out,      // J18 -- read only, never driven
    input  wire uart_txd_in,       // J17 -- read only, never driven
    output wire [1:0] led
);
    // Two-flop synchronisers. These pins are asynchronous to clk by definition,
    // and sampling them straight into logic would be metastable -- which for a
    // measurement instrument would mean an unreadable LED at exactly the moment
    // the answer matters.
    reg [1:0] sync_rxd = 2'b00;
    reg [1:0] sync_txd = 2'b00;
    always @(posedge clk) begin
        sync_rxd <= {sync_rxd[0], uart_rxd_out};
        sync_txd <= {sync_txd[0], uart_txd_in};
    end

    // One free-running counter; two of its bits are the two blink rates.
    // At 12 MHz: bit 21 toggles at ~2.9 Hz, bit 23 at ~0.7 Hz.
    reg [23:0] cnt = 24'd0;
    always @(posedge clk) cnt <= cnt + 24'd1;

    wire fast = cnt[21];
    wire slow = cnt[23];

    assign led[0] = sync_rxd[1] ? fast : slow;
    assign led[1] = sync_txd[1] ? fast : slow;
endmodule
`default_nettype wire
