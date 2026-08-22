// Testbench for the pin-activity probe.
//
// The previous, static-level version of this probe was shipped without a
// simulation, went to hardware, and returned no answer at all -- both LEDs fast,
// which was the "inconclusive" case. This one gets checked first.
//
// The property under test is the only one that matters: a pin carrying edges
// must read active, and a pin held at a constant level -- EITHER level, since a
// board pull-up parks one high and that is precisely what defeated the earlier
// attempt -- must read inactive.
//
// The window counter is scaled down via WINDOW_BITS so the test can cross
// several activity windows quickly. Hardware behaviour is identical.
`timescale 1ns/1ps

module tb_pinprobe;
    localparam integer WB     = 12;              // 4096-cycle window
    localparam integer WINDOW = (1 << WB);

    reg clk = 1'b0;
    always #1 clk = ~clk;

    reg moving      = 1'b0;
    reg parked_high = 1'b1;      // the pull-up case that broke the last probe
    wire [1:0] led;

    pinprobe #(.WINDOW_BITS(WB)) dut (
        .clk(clk),
        .uart_rxd_out(moving),
        .uart_txd_in(parked_high),
        .led(led)
    );

    // Traffic on one pin only, at roughly UART edge rates relative to the clock.
    always #21 moving = ~moving;

    integer errors = 0;

    task check(input cond, input [511:0] what);
        begin
            if (cond) $display("PASS  %0s", what);
            else begin $display("FAIL  %0s", what); errors = errors + 1; end
        end
    endtask

    // Cross at least two window boundaries, so what is observed is a settled
    // steady state rather than whatever the previous window happened to latch.
    task settle;
        begin repeat (3 * WINDOW) @(posedge clk); end
    endtask

    initial begin
        settle;

        check(dut.act_rxd === 1'b1, "moving pin registers as active");
        check(dut.act_txd === 1'b0, "pin parked HIGH registers as inactive");
        check(dut.act_rxd !== dut.act_txd,
              "moving and parked pins are distinguishable -- the whole point");

        // A pin parked LOW must also read inactive: level is never the signal.
        // Changing it is itself one real edge, so let that wash out first.
        parked_high = 1'b0;
        settle;
        check(dut.act_txd === 1'b0, "pin parked LOW also registers as inactive");

        // Activity must decay. Without this the display would latch a single
        // stray edge forever and report traffic that stopped minutes ago.
        force dut.sync_rxd = 2'b00;
        settle;
        check(dut.act_rxd === 1'b0, "activity decays once traffic stops");

        // And recover: a pin that goes quiet and busy again must read active
        // again, or the probe would be a one-shot.
        release dut.sync_rxd;
        settle;
        check(dut.act_rxd === 1'b1, "activity is detected again when traffic resumes");

        if (errors == 0)
            $display("\nPINPROBE OK - edges detected, static levels ignored, decays and recovers");
        else
            $display("\n%0d CHECK(S) FAILED", errors);
        $finish;
    end
endmodule
