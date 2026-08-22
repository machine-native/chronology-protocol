# Cmod A7-35T constraints — from the Digilent reference XDC for this board.
# Only the pins this design uses are enabled.

## 12 MHz on-board oscillator
set_property -dict { PACKAGE_PIN L17  IOSTANDARD LVCMOS33 } [get_ports { clk }];
create_clock -add -name sys_clk_pin -period 83.33 -waveform {0 41.66} [get_ports { clk }];

## USB-UART bridge (FT2232H). Digilent's naming is from the BRIDGE's point of view:
##   uart_rxd_out = bridge output  -> FPGA input   (host to FPGA)
##   uart_txd_in  = bridge input   <- FPGA output  (FPGA to host)
set_property -dict { PACKAGE_PIN J18  IOSTANDARD LVCMOS33 } [get_ports { uart_rxd_out }];
set_property -dict { PACKAGE_PIN J17  IOSTANDARD LVCMOS33 } [get_ports { uart_txd_in  }];

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
