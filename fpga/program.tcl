# Program the Cmod A7-35T from the command line, and say plainly whether it worked.
#
#     vivado -mode batch -source program.tcl
#
# Clicking through Hardware Manager works too, but it leaves "was the device
# actually programmed?" as a question answered by remembering what a dialog said.
# This answers it with a readback, and then closes the JTAG session -- which
# matters on this board, because JTAG and the UART are two channels of the SAME
# FT2232 chip and an open target can hold the serial port shut.
#
# Programming is VOLATILE. It survives until power is removed. Unplugging the
# board to look for its COM port erases it.

set bitfile [file normalize ./build/miner_top.bit]

if {![file exists $bitfile]} {
    puts "\nERROR: no bitstream at $bitfile"
    puts "Build it first:  vivado -mode batch -source build.tcl\n"
    exit 1
}

open_hw_manager
connect_hw_server

if {[llength [get_hw_targets]] == 0} {
    puts "\nERROR: no JTAG target found."
    puts "The board is unplugged, or the Digilent USB drivers are not installed."
    puts "Drivers ship with Vivado: <install>/data/xicom/cable_drivers\n"
    disconnect_hw_server
    exit 1
}

open_hw_target
set dev [lindex [get_hw_devices] 0]
current_hw_device $dev
refresh_hw_device -update_hw_probes false $dev
puts "\ndevice found : [get_property PART $dev]"

set_property PROGRAM.FILE $bitfile $dev
program_hw_devices $dev
refresh_hw_device -update_hw_probes false $dev

# Read the state back rather than trusting that the command returned quietly.
set done [get_property REGISTER.IR.BIT5_DONE $dev]
puts "bitstream    : $bitfile"
puts "DONE pin     : $done"

# Release the FT2232 before anyone tries to open the serial port.
close_hw_target
disconnect_hw_server
close_hw_manager

if {$done eq "1"} {
    puts "\n=== PROGRAMMED ==="
    puts "LED0 should now be blinking once a second. If it is not, the clock or"
    puts "the CLK_HZ parameter is wrong -- fix that before blaming the UART."
    puts "Then:  py ..\\scripts\\fpga_diag.py --port COM4\n"
    exit 0
}

puts "\n=== PROGRAMMING FAILED ==="
puts "DONE did not assert. The bitstream did not take; the device is not running.\n"
exit 1
