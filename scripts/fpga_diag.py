#!/usr/bin/env python3
"""Diagnose a silent FPGA UART link, one hypothesis at a time.

`ping` failing tells you almost nothing on its own — wrong port, unprogrammed
device, wrong baud and dead wiring all look identical. This walks the
possibilities in order and reports what it actually observed.

Usage:
  python scripts/fpga_diag.py              # list candidate ports
  python scripts/fpga_diag.py --port COM7  # probe one port properly
"""
from __future__ import annotations
import argparse, sys, time


def list_ports():
    try:
        from serial.tools import list_ports
    except ImportError:
        raise SystemExit("pyserial required:  py -m pip install pyserial")
    ports = list(list_ports.comports())
    if not ports:
        print("NO SERIAL PORTS FOUND.")
        print("  The board is unplugged, or the FTDI VCP driver is missing.")
        print("  Driver: https://ftdichip.com/drivers/vcp-drivers/")
        return []
    print(f"{len(ports)} serial port(s):\n")
    for p in ports:
        print(f"  {p.device:<8} {p.description}")
        print(f"           hwid: {p.hwid}")
        if "0403" in (p.hwid or ""):          # FTDI vendor id
            print("           ^ FTDI — this is very likely the board")
    print("\nProbe one with:  python scripts/fpga_diag.py --port COM7")
    return ports


def probe(port: str):
    try:
        import serial
    except ImportError:
        raise SystemExit("pyserial required:  py -m pip install pyserial")

    print(f"probing {port}\n")

    # 1. can we even open it?
    try:
        ser = serial.Serial(port, 115200, timeout=1.5)
    except Exception as e:
        print(f"FAIL  cannot open the port: {e}")
        print("      Something else may hold it open — close any serial terminal,")
        print("      and close Vivado's Hardware Manager if it is running.")
        return False
    print("ok    port opens")

    # 2. does anything answer at the design's baud?
    ser.reset_input_buffer()
    ser.write(b"P")
    time.sleep(0.3)
    reply = ser.read(16)
    if reply == b"K":
        print("ok    ping answered 'K' — the link is good")
        ser.close()
        return True
    if reply:
        print(f"?     something replied, but not 'K': {reply!r}")
        print("      Bytes at the wrong baud usually look like this.")
    else:
        print("none  no reply at 115200")

    # 3. is anything alive at another baud? a wrong CLK_HZ generic shows up here
    print("\nsweeping other baud rates for any traffic at all:")
    found_any = False
    for baud in (9600, 19200, 38400, 57600, 230400, 460800):
        try:
            ser.baudrate = baud
            ser.reset_input_buffer()
            ser.write(b"P")
            time.sleep(0.25)
            data = ser.read(16)
            if data:
                found_any = True
                print(f"  {baud:>7}: {data!r}   <-- traffic here")
            else:
                print(f"  {baud:>7}: silent")
        except Exception as e:
            print(f"  {baud:>7}: error {e}")
    ser.close()

    print()
    if found_any:
        print("VERDICT: the FPGA is alive but the baud does not match.")
        print("  The bitstream's CLK_HZ/BAUD generics likely differ from the board.")
    else:
        print("VERDICT: total silence. In order of likelihood:")
        print("  1. The bitstream is not loaded. Hardware Manager programming is")
        print("     VOLATILE — any unplug or power cycle erases it. Re-program and")
        print("     do NOT unplug before testing.")
        print("  2. Wrong COM port — run without --port to list them.")
        print("  3. The device was programmed but configuration failed; check that")
        print("     Hardware Manager still shows it as programmed.")
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port")
    a = ap.parse_args()
    if a.port:
        sys.exit(0 if probe(a.port) else 1)
    list_ports()


if __name__ == "__main__":
    main()
