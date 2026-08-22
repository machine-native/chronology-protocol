# Constraints for the pin-direction probe. Same pins as the miner, but BOTH
# UART nets are inputs here and neither is ever driven by the FPGA.

## 12 MHz on-board oscillator
set_property -dict { PACKAGE_PIN L17  IOSTANDARD LVCMOS33 } [get_ports { clk }];
create_clock -add -name sys_clk_pin -period 83.33 -waveform {0 41.66} [get_ports { clk }];

## The two USB-UART nets, read only.
## PULLTYPE PULLDOWN is the entire measurement: a weak pulldown loses to the
## bridge's active driver and wins against an undriven pin, so the pin that
## reads high is the one the bridge transmits on.
set_property -dict { PACKAGE_PIN J18  IOSTANDARD LVCMOS33  PULLTYPE PULLDOWN } [get_ports { uart_rxd_out }];
set_property -dict { PACKAGE_PIN J17  IOSTANDARD LVCMOS33  PULLTYPE PULLDOWN } [get_ports { uart_txd_in  }];

## LD1 reports J18, LD2 reports J17. Fast flicker = high, slow blink = low.
set_property -dict { PACKAGE_PIN A17  IOSTANDARD LVCMOS33 } [get_ports { led[0] }];
set_property -dict { PACKAGE_PIN C16  IOSTANDARD LVCMOS33 } [get_ports { led[1] }];

## Configuration
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]
set_property CONFIG_MODE SPIx4 [current_design]
