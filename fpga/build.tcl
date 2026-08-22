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

# The board's oscillator is 12 MHz; the RTL defaults match, but state it once
# here so a change is visible in one place.
#
# These are passed to synth_design directly rather than set on the fileset.
# `set_property generic ... [current_fileset]` is a project-flow idiom, and in
# an -in_memory project it can be accepted without taking effect -- which would
# silently fall back to the RTL defaults. They happen to be identical today, so
# the failure would be invisible now and load-bearing the moment someone changes
# one. -generic is the documented path for this flow and errors if misused.
set generics [list CLK_HZ=12000000 BAUD=115200 ZERO_WORDS=1]
puts "generics  : $generics"

synth_design -top $top -part $part \
    -generic CLK_HZ=12000000 \
    -generic BAUD=115200 \
    -generic ZERO_WORDS=1
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

puts "\n=== BUILD COMPLETE ==="
puts "bitstream : $outdir/${top}.bit"
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
