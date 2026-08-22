# Constraints for the pin-direction probe. Same pins as the miner, but BOTH
# UART nets are inputs here and neither is ever driven by the FPGA.

## 12 MHz on-board oscillator
set_property -dict { PACKAGE_PIN L17  IOSTANDARD LVCMOS33 } [get_ports { clk }];
create_clock -add -name sys_clk_pin -period 83.33 -waveform {0 41.66} [get_ports { clk }];

## The two USB-UART nets, read only.
##
## The pulldowns are no longer the measurement -- comparing static levels was
## tried first and came back with BOTH pins high, because a weak internal
## pulldown cannot outvote a board pull-up resistor and so cannot tell a driven
## pin from a parked one. The probe now watches for EDGES instead.
##
## They are kept because an undriven CMOS input floats and will register noise
## as edges, which in an activity detector is a false positive on the exact
## question being asked. Here the pulldown parks the quiet pin quiet.
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
