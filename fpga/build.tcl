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

# The board's oscillator is 12 MHz; the RTL default matches, but state it once
# here so a change is visible in one place.
set_property generic {CLK_HZ=12000000 BAUD=115200 ZERO_WORDS=1} [current_fileset]

synth_design -top $top -part $part
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

puts "\n=== BUILD COMPLETE ==="
puts "bitstream : $outdir/${top}.bit"
puts "check     : $outdir/utilisation.rpt (LUT usage) and $outdir/timing.rpt (WNS must be positive)"
