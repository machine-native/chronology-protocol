// Pin-activity probe for the Cmod A7 USB-UART bridge. Not part of the miner.
//
// WHY THIS EXISTS
//
// The miner's bitstream loads, meets timing with 69 ns to spare, and blinks its
// heartbeat -- yet the serial link is silent in BOTH directions at seven baud
// rates. That is what a transmit/receive mix-up looks like, and there are two
// independent ways to have one:
//
//   1. the DIRECTIONS are swapped -- Digilent's net names `uart_rxd_out` and
//      `uart_txd_in` can be read as relative to the bridge or to the host, and
//      both readings are grammatical;
//   2. the PACKAGE PINS are swapped -- J17 and J18 assigned to the wrong nets.
//
// Silence cannot tell these apart, and neither can a datasheet argument.
//
// WHAT THE FIRST VERSION GOT WRONG
//
// This probe originally compared STATIC pin levels: weak internal pulldowns, on
// the theory that the bridge's transmit pin idles actively high and wins, while
// its receive pin is undriven and loses. On hardware BOTH pins read high, which
// is no answer at all. A weak pulldown cannot distinguish a pin driven high by
// the bridge from one held high by a board pull-up resistor -- and UART lines
// commonly have those. The measurement was too weak for the question.
//
// HOW THIS VERSION WORKS
//
// Motion, not level. While the host transmits a continuous byte stream, the
// bridge's transmit pin TOGGLES; its receive pin is an input on the bridge's
// side and stays still, whatever DC level a resistor parks it at. A pull-up
// cannot fake an edge.
//
// So: detect edges on each pin, latch them within a rolling ~1.4 s window, and
// show the result. Both pins are still declared INPUTS and neither is ever
// driven, so this remains safe to run without knowing the answer.
//
//   The pin that MOVES is the bridge's output, and therefore the FPGA's RX.
//
// READING THE RESULT -- first start the host stream:
//
//     py scripts/fpga_diag.py --port COM4 --stream
//
//   FAST flicker (~3 Hz) = edges seen on that pin = the bridge is driving it
//   SLOW blink  (~0.7 Hz) = that pin is static
//
//   LD1 = uart_rxd_out (J18)      LD2 = uart_txd_in (J17)
//
//   LD1 fast, LD2 slow -> declarations are CORRECT; the fault is elsewhere
//   LD1 slow, LD2 fast -> RX and TX are crossed; that is the bug
//   both slow          -> nothing arrives on either pin. COM4 is not wired to
//                         them: wrong port, or the bridge's second channel
//   both fast          -> both pins carry traffic, which should be impossible
//                         with the FPGA driving neither; report it
//
// Every LED state blinks, so a dark board still means "no bitstream" and can
// never be misread as a measurement.
//
// RESULT, 2026-08-22: LD1 slow, LD2 fast. J17 carried the host's traffic and
// J18 was static, so the FPGA receives on J17 and transmits on J18. The
// constraints file had the two package pins the other way round; that, and not
// the direction convention, was the bug. The naming argument had been running
// for three build cycles against the wrong question.
//
// This probe is kept rather than deleted: it is the cheapest way to re-confirm
// the mapping on a different board or revision, and it is the record of how the
// answer was obtained.
`default_nettype none

module pinprobe #(
    // Width of the free-running window/blink counter. 24 bits at 12 MHz gives a
    // ~1.4 s activity window and blink rates an eye can read. Simulation scales
    // it down so a testbench can cross several windows in reasonable time --
    // the hardware behaviour is identical, only the timebase changes.
    parameter integer WINDOW_BITS = 24
) (
    input  wire clk,
    // Named by PACKAGE PIN, because the pin is what this instrument measures.
    // Using the net names here would import the very ambiguity it exists to
    // resolve. Neither is ever driven.
    input  wire pin_j18,
    input  wire pin_j17,
    output wire [1:0] led
);
    // Two-flop synchronisers. These pins are asynchronous to clk by definition;
    // sampling them straight into logic would be metastable, which in a
    // measuring instrument means an unreadable answer exactly when it matters.
    reg [1:0] sync_j18 = 2'b00;
    reg [1:0] sync_j17 = 2'b00;
    reg       prev_j18 = 1'b0;
    reg       prev_j17 = 1'b0;

    // Free-running window and blink-rate source. At 12 MHz a 24-bit counter
    // wraps every ~1.4 s: bit 21 toggles at ~2.9 Hz, bit 23 at ~0.7 Hz.
    reg [WINDOW_BITS-1:0] cnt = {WINDOW_BITS{1'b0}};

    // Sticky within the window, so a burst of edges is still visible to an eye
    // rather than flashing past between two clock cycles.
    reg act_j18 = 1'b0;
    reg act_j17 = 1'b0;

    // Startup blanking. The synchronisers and `prev` registers power up at 0,
    // so a pin sitting HIGH -- which is every idle UART line, and every line
    // with a pull-up -- presents a 0->1 transition on the first samples that is
    // an artefact of reset, not traffic. Without this, both pins latch a
    // phantom edge and the probe reports activity everywhere for a full window:
    // exactly the "both fast" non-answer this instrument exists to avoid.
    // Simulation caught it; the previous probe went to hardware unsimulated and
    // came back meaningless.
    reg [3:0] arm = 4'd0;
    wire armed = (arm == 4'hF);

    always @(posedge clk) begin
        sync_j18 <= {sync_j18[0], pin_j18};
        sync_j17 <= {sync_j17[0], pin_j17};
        prev_j18 <= sync_j18[1];
        prev_j17 <= sync_j17[1];
        cnt      <= cnt + {{(WINDOW_BITS-1){1'b0}}, 1'b1};
        if (!armed) arm <= arm + 4'd1;

        if (!armed) begin
            act_j18 <= 1'b0;
            act_j17 <= 1'b0;
        end else if (cnt == {WINDOW_BITS{1'b0}}) begin
            // window boundary: forget the last window so the display tracks
            // live traffic instead of latching one stray edge forever
            act_j18 <= 1'b0;
            act_j17 <= 1'b0;
        end else begin
            if (sync_j18[1] != prev_j18) act_j18 <= 1'b1;
            if (sync_j17[1] != prev_j17) act_j17 <= 1'b1;
        end
    end

    wire fast = cnt[WINDOW_BITS-3];   // ~2.9 Hz at 12 MHz
    wire slow = cnt[WINDOW_BITS-1];   // ~0.7 Hz at 12 MHz

    assign led[0] = act_j18 ? fast : slow;
    assign led[1] = act_j17 ? fast : slow;
endmodule
`default_nettype wire
