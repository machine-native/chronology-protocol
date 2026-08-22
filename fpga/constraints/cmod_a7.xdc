# Cmod A7-35T constraints — from the Digilent reference XDC for this board.
# Only the pins this design uses are enabled.

## 12 MHz on-board oscillator
set_property -dict { PACKAGE_PIN L17  IOSTANDARD LVCMOS33 } [get_ports { clk }];
create_clock -add -name sys_clk_pin -period 83.33 -waveform {0 41.66} [get_ports { clk }];

## USB-UART bridge (FT2232H).
##
## These two assignments were MEASURED, not read off a datasheet. An earlier
## version had them the other way round and the link was silent in both
## directions for several build cycles, while the argument stayed stuck on
## whether Digilent's `uart_rxd_out` / `uart_txd_in` names are relative to the
## bridge or the host. That was the wrong question: the naming convention was
## being read correctly all along, and the PACKAGE PINS were simply swapped.
##
## The measurement (fpga/rtl/pinprobe.v, 2026-08-22): with the host transmitting
## continuously, J17 showed edges and J18 stayed static. Traffic from the host
## arrives on J17, so that is the FPGA's receive pin. Nothing about this depends
## on what the nets are called.
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
