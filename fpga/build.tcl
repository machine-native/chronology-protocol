# Vivado batch build for the Cmod A7-35T miner.
#
# Run from this directory on a machine with Vivado installed:
#
#     vivado -mode batch -source build.tcl
#
# Produces ./build/miner_top.bit plus a utilisation and timing report. Nothing
# here is interactive, so the result is reproducible and diffable.

set part      xc7a35tcpg236-1
set top       miner_top
set outdir    [file normalize ./build]
file mkdir $outdir

create_project -in_memory -part $part

read_verilog [glob ./rtl/*.v]
read_xdc     ./constraints/cmod_a7.xdc

# Core count and clock frequency are the two knobs worth sweeping, so they are
# command-line arguments rather than RTL edits:
#
#     vivado -mode batch -source build.tcl -tclargs <cores> <MHz>
#     vivado -mode batch -source build.tcl -tclargs 8 60       (the default)
#
# The board oscillator is 12 MHz; an MMCM multiplies it to CLK_HZ via a fixed
# 600 MHz VCO (see the reachability check below). Core count and clock trade
# against each other: one core alone closed at ~76 MHz, and the 8-core build
# measured 70.4 MHz fmax, so filling the fabric costs real frequency. That
# trade is why this is swept rather than assumed -- read the WNS printed at the
# end, and do not trust any rate measured from a build with negative slack.
#
# Generics go to synth_design directly rather than onto the fileset.
# `set_property generic ... [current_fileset]` is a project-flow idiom that an
# -in_memory project can accept without effect, which would silently fall back
# to the RTL defaults -- invisible while they happen to match, load-bearing the
# moment they do not. -generic is the documented path here and errors if misused.
set cores 8
set mhz   60
if {[llength $argv] >= 1} { set cores [lindex $argv 0] }
if {[llength $argv] >= 2} { set mhz   [lindex $argv 1] }

# CLKOUT0_DIVIDE_F is a real with 0.125 granularity, so the reachable set is
# wider than the integer divisors of 600: 69.565 MHz (divide 8.625) is legal
# where 70 is not. Check what the part can actually synthesise rather than a
# stricter rule of thumb -- rejecting a frequency the hardware supports is as
# much a defect as accepting one it does not, and this board's measured fmax of
# 70.4 MHz sits precisely in the gap the stricter rule would have hidden.
set div [expr {600.0 / $mhz}]
if {abs($div * 8 - round($div * 8)) > 0.01 || $div < 1.0 || $div > 128.0} {
    puts "\nERROR: $mhz MHz is not reachable from the 600 MHz VCO."
    puts "CLKOUT0_DIVIDE_F moves in steps of 0.125, so 600/f must land on one."
    puts "Reachable nearby: 50, 60, 66.667, 69.565, 75, 100 MHz\n"
    exit 1
}
# round(): a fractional MHz such as 69.565 would otherwise make clk_hz a float,
# and the generic must be an integer number of hertz.
set clk_hz [expr {round($mhz * 1000000)}]

puts "cores     : $cores"
puts "clock     : $mhz MHz  (CLK_HZ=$clk_hz)"

synth_design -top $top -part $part \
    -generic CLK_HZ=$clk_hz \
    -generic BAUD=115200 \
    -generic ZERO_WORDS=1 \
    -generic NUM_CORES=$cores
write_checkpoint -force $outdir/post_synth.dcp
report_utilization -file $outdir/utilisation_synth.rpt

opt_design
place_design
phys_opt_design
route_design

write_checkpoint -force $outdir/post_route.dcp
report_utilization      -file $outdir/utilisation.rpt
report_timing_summary   -file $outdir/timing.rpt
report_drc              -file $outdir/drc.rpt

write_bitstream -force $outdir/${top}.bit

# Report the numbers that decide whether this build is usable, rather than
# leaving them in a file the reader may not open.
#
# Setup and hold must be read SEPARATELY. An earlier version of this script
# asked for -delay_type min_max and printed the single worst slack, which
# reported 0.024 ns on a build whose real setup margin was 69.588 ns -- the
# 0.024 was the hold path, where small positive slack is normal and expected.
# One number for two different questions is how a healthy build gets mistaken
# for a marginal one.
set wns [get_property SLACK [get_timing_paths -delay_type max]]
set whs [get_property SLACK [get_timing_paths -delay_type min]]

# Projected throughput for the configuration actually built. 132 cycles per
# nonce per core was confirmed against hardware to within 0.3%, so this is
# arithmetic on a measured constant rather than on a guess -- but it is still a
# projection, and the selftest below is what turns it into a measurement.
set mhs [expr {double($cores) * $clk_hz / 132.0 / 1000000.0}]

puts "\n=== BUILD COMPLETE ==="
puts "bitstream : $outdir/${top}.bit"
puts "config    : $cores cores at $mhz MHz"
puts [format "projected : %.2f MH/s  -- confirm with: fpga_host.py selftest --depth 5000000" $mhs]
puts "WNS setup : $wns ns   (margin against the clock period)"
puts "WHS hold  : $whs ns   (small positive is normal)"
if {$whs < 0} {
    puts "\nWARNING: HOLD VIOLATION -- the design will not work in hardware.\n"
}
if {$wns < 0} {
    puts "\nWARNING: NEGATIVE SLACK -- this design does not meet timing."
    puts "Do not trust hardware results from this bitstream.\n"
} else {
    puts "timing    : met"
    puts "\nNext:  vivado -mode batch -source program.tcl\n"
}
