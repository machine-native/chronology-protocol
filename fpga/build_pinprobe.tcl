# Build AND program the pin-direction probe in one pass.
#
#     vivado -mode batch -source build_pinprobe.tcl
#
# Tiny design, so synthesis takes well under a minute. It writes to build_probe/
# so it cannot overwrite the miner's bitstream, and it programs the board itself
# because the whole point is to get an answer with the fewest steps.
#
# This is a measuring instrument, not part of the miner. It drives neither UART
# pin, so it is safe to run without knowing which direction is correct -- which
# is precisely the question it answers.

set part   xc7a35tcpg236-1
set top    pinprobe
set outdir [file normalize ./build_probe]
file mkdir $outdir

create_project -in_memory -part $part
read_verilog ./rtl/pinprobe.v
read_xdc     ./constraints/pinprobe.xdc

synth_design -top $top -part $part
opt_design
place_design
route_design
write_bitstream -force $outdir/${top}.bit

puts "\nprobe bitstream : $outdir/${top}.bit"

# ---- program it ----------------------------------------------------------
open_hw_manager
connect_hw_server

if {[llength [get_hw_targets]] == 0} {
    puts "\nERROR: no JTAG target found -- is the board plugged in?\n"
    disconnect_hw_server
    exit 1
}

open_hw_target
set dev [lindex [get_hw_devices] 0]
current_hw_device $dev
refresh_hw_device -update_hw_probes false $dev
set_property PROGRAM.FILE $outdir/${top}.bit $dev
program_hw_devices $dev
refresh_hw_device -update_hw_probes false $dev
set done [get_property REGISTER.IR.BIT5_DONE $dev]

# Release the FT2232 before the bridge is asked to do anything.
close_hw_target
disconnect_hw_server
close_hw_manager

if {$done ne "1"} {
    puts "\n=== PROGRAMMING FAILED === DONE did not assert.\n"
    exit 1
}

puts "\n================ PROBE RUNNING ================"
puts ""
puts "  LD1 = J18 (uart_rxd_out)     LD2 = J17 (uart_txd_in)"
puts ""
puts "  FAST flicker ~3 Hz  = pin is HIGH = the bridge drives it"
puts "  SLOW blink  ~0.7 Hz = pin is LOW  = nothing drives it"
puts ""
puts "  LD1 fast, LD2 slow  -> pin directions are CORRECT as written"
puts "  LD1 slow, LD2 fast  -> pins are SWAPPED  <- the bug"
puts "  both slow           -> bridge drives neither; wrong COM port entirely"
puts "  both fast           -> inconclusive; report it"
puts ""
puts "  Watch for ten seconds and report which LED is which."
puts "==============================================="
puts ""
exit 0
