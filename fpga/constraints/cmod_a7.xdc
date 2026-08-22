# Cmod A7-35T constraints — from the Digilent reference XDC for this board.
# Only the pins this design uses are enabled.

## 12 MHz on-board oscillator
set_property -dict { PACKAGE_PIN L17  IOSTANDARD LVCMOS33 } [get_ports { clk }];
create_clock -add -name sys_clk_pin -period 83.33 -waveform {0 41.66} [get_ports { clk }];

## USB-UART bridge (FT2232H).
##
## These two assignments were MEASURED, not read off a datasheet.
## fpga/rtl/pinprobe.v, 2026-08-22: with the host transmitting continuously, J17
## showed edges and J18 stayed static. Traffic from the host arrives on J17, so
## that is the FPGA's receive pin -- whatever anyone chooses to call the net.
##
## What was actually wrong before: the PIN NUMBERS matched Digilent's master XDC
## exactly (J18 = uart_rxd_out, J17 = uart_txd_in). The DIRECTIONS were inverted.
## Digilent's names are relative to the HOST/USB side, so `uart_txd_in` is data
## transmitted BY the host INTO the board -- an FPGA input -- and `uart_rxd_out`
## is what the board sends back. They were declared the other way round.
##
## The cost of that: the FPGA drove J17 as an output while the FT2232 was also
## driving it. Two push-pull CMOS drivers fighting, for as long as the board was
## powered with that bitstream loaded.
set_property -dict { PACKAGE_PIN J17  IOSTANDARD LVCMOS33 } [get_ports { uart_rx_from_host }];
set_property -dict { PACKAGE_PIN J18  IOSTANDARD LVCMOS33 } [get_ports { uart_tx_to_host   }];

## Two of the on-board LEDs: led[0] = 1 Hz heartbeat, led[1] = scanning.
## The heartbeat is a bring-up instrument: it proves the bitstream is loaded and
## the clock is running before any question about the serial link is asked.
set_property -dict { PACKAGE_PIN A17  IOSTANDARD LVCMOS33 } [get_ports { led[0] }];
set_property -dict { PACKAGE_PIN C16  IOSTANDARD LVCMOS33 } [get_ports { led[1] }];

## Configuration
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]
set_property CONFIG_MODE SPIx4 [current_design]
