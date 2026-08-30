#!/usr/bin/env python3
"""Diagnose a silent FPGA UART link, one hypothesis at a time.

`ping` failing tells you almost nothing on its own — wrong port, unprogrammed
device, wrong baud and dead wiring all look identical. This walks the
possibilities in order and reports what it actually observed.

Usage:
  python scripts/fpga_diag.py                      # list candidate ports
  python scripts/fpga_diag.py --port COM7          # probe one port properly
  python scripts/fpga_diag.py --port COM7 --stream # transmit continuously
"""
from __future__ import annotations
import argparse, sys, time


def stream(port: str, seconds: int, baud: int):
    """Transmit continuously so the pin-activity probe has something to see.

    The FPGA-side probe answers "which package pin carries host traffic?" by
    watching for edges. That question only has an answer while the host is
    actually transmitting, and a one-shot ping is over in 87 microseconds --
    far too brief to see on an LED. This holds the line busy long enough to
    walk over to the board and look at it.

    0x55 is chosen deliberately: alternating bits give the maximum number of
    edges per byte, so a pin carrying it cannot be mistaken for a static one.
    """
    try:
        import serial
    except ImportError:
        raise SystemExit("pyserial required:  py -m pip install pyserial")

    try:
        ser = serial.Serial(port, baud, timeout=0.1)
    except Exception as e:
        print(f"FAIL  cannot open {port}: {e}")
        return False

    print(f"streaming 0x55 to {port} at {baud} baud for {seconds}s\n")
    print("  Watch the two LEDs on the board now:")
    print("    FAST flicker = that pin is carrying the traffic  (the FPGA's RX)")
    print("    SLOW blink   = that pin is static")
    print("    LD1 = J18 (uart_rxd_out)     LD2 = J17 (uart_txd_in)\n")

    block = b"\x55" * 256
    end = time.monotonic() + seconds
    sent = 0
    try:
        while time.monotonic() < end:
            ser.write(block)
            sent += len(block)
            remaining = int(end - time.monotonic())
            print(f"\r  sent {sent:,} bytes   {remaining:>3}s left ", end="", flush=True)
    except KeyboardInterrupt:
        print("\n  stopped")
    except Exception as e:
        print(f"\nFAIL  write failed after {sent} bytes: {e}")
        ser.close()
        return False
    ser.close()

    print(f"\n\n  done -- {sent:,} bytes written without error.")
    print("  Note this proves the HOST sent them; only the LEDs can say whether")
    print("  they reached the FPGA's pins.")
    return True


def list_ports():
    try:
        from serial.tools import list_ports
    except ImportError:
        raise SystemExit("pyserial required:  py -m pip install pyserial")
    ports = list(list_ports.comports())
    if not ports:
        print("NO SERIAL PORTS FOUND.")
        print()
        print("  Which driver you need depends on the chip, and they are not")
        print("  interchangeable. Check the chip printed on the board:")
        print("    Silicon Labs CP2102  -> CP210x VCP driver")
        print("      https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers")
        print("    FTDI FT232           -> FTDI VCP driver")
        print("      https://ftdichip.com/drivers/vcp-drivers/")
        print("    CH340 / CH341        -> WCH CH341SER driver")
        print()
        print("  But check enumeration FIRST -- a missing driver shows up as an")
        print("  unrecognised device, not as nothing at all. In PowerShell:")
        print("    Get-PnpDevice -PresentOnly | ? { $_.Class -in 'Ports','USB' }")
        print("  If the board does not appear there at all, it is not a driver")
        print("  problem: the plug is not seated, the port is dead, the cable is")
        print("  power-only, or the board is faulty. Installing a driver will not")
        print("  help, and trying it first wastes the evening.")
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
    ap.add_argument("--stream", action="store_true",
                    help="transmit 0x55 continuously so the FPGA pin probe has "
                         "traffic to detect; watch the board's LEDs while it runs")
    ap.add_argument("--seconds", type=int, default=30)
    ap.add_argument("--baud", type=int, default=115200)
    a = ap.parse_args()
    if a.stream:
        if not a.port:
            raise SystemExit("--stream needs --port, e.g. --port COM4 --stream")
        sys.exit(0 if stream(a.port, a.seconds, a.baud) else 1)
    if a.port:
        sys.exit(0 if probe(a.port) else 1)
    list_ports()


if __name__ == "__main__":
    main()
