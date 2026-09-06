#!/usr/bin/env python3
"""Broadcast anchor-chain blocks over a REYAX RYLR998 LoRa module.

This is the hardware driver for the CHRN radio profile in ctp/radio.py. That
module does the framing and decides what is acceptable; this one only moves
bytes over a radio. The separation matters: a block is self-authenticating, so
the receiver validates proof-of-work locally and never has to trust the link,
the sender, or this program.

Modes:
  probe     ask the module what it is and what it is set to, and print the
            answers verbatim. Run this first.
  config    set network id, address and band
  send      fragment a raw block and transmit it
  receive   listen, reassemble, validate proof-of-work, write out valid blocks

Usage:
  python scripts/lora_relay.py probe   --port COM5
  python scripts/lora_relay.py config  --port COM5 --address 1 --band 865000000
  python scripts/lora_relay.py send    --port COM5 --block live/mine/xyz.json
  python scripts/lora_relay.py receive --port COM5 --out live/radio-received/

TWO CONSTRAINTS THAT SHAPE EVERYTHING HERE
------------------------------------------

1. `AT+SEND` carries ASCII, not binary. CHRB fragments are raw bytes, so they
   are hex-encoded on the wire, which doubles their size. This is not elegant
   and it is not optional: a raw 0x0D or 0x0A inside an AT command terminates
   the command early, and a raw 0x00 truncates it. Hex is the cheapest encoding
   that cannot collide with the command syntax.

2. The module's maximum payload is smaller than LoRa's. ctp/radio.py defaults to
   a 255-byte MTU, which is the LoRa air limit; the RYLR998's AT interface caps a
   send at 240 ASCII characters. After hex-encoding that is 120 binary bytes, so
   the MTU used here is 120 -- 109 bytes of block per fragment after the 11-byte
   CHRB header. A 306-byte anchor block becomes 3 fragments.

WHAT IS ASSUMED AND WHAT IS MEASURED
------------------------------------

The AT command set below is from the RYLR998 documentation. It has NOT been
confirmed against the module yet. That is exactly why `probe` exists and why it
prints raw responses instead of interpreting them: the last hardware bring-up in
this project lost three build cycles to a datasheet reading that was confidently
wrong, and the fix was to make the hardware answer rather than argue about it.

If `probe` disagrees with anything documented here, believe `probe`.
"""
from __future__ import annotations
import argparse, hashlib, json, socket, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ctp.radio import fragment, Reassembler, pow_valid, HEADER_LEN
from ctp.bitcoin_jan09 import block_hash

# AT+SEND takes at most 240 ASCII characters. Hex doubles, so 120 binary bytes.
RYLR_MAX_ASCII = 240
LORA_MTU = RYLR_MAX_ASCII // 2          # 120 bytes of CHRB frame
BROADCAST = 0                            # RYLR: address 0 reaches every node
                                         # on the same NETWORKID. Confirm with probe.


def open_port(port: str, baud: int = 115200):
    try:
        import serial
    except ImportError:
        raise SystemExit("pyserial required:  py -m pip install pyserial")
    return serial.Serial(port, baud, timeout=2)


def at(ser, command: str, wait: float = 0.5) -> list[str]:
    """Send one AT command and return every line the module replies with.

    Returns the lines uninterpreted. Callers that need a decision make it
    themselves; this function does not decide whether a reply means success,
    because the failure modes are more interesting than a boolean.
    """
    ser.reset_input_buffer()
    ser.write((command + "\r\n").encode("ascii"))
    ser.flush()
    deadline = time.time() + wait
    lines, buf = [], b""
    while time.time() < deadline:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                text = line.strip().decode("ascii", errors="replace")
                if text:
                    lines.append(text)
            deadline = time.time() + 0.15      # more may follow
    return lines


def cmd_probe(a):
    ser = open_port(a.port, a.baud)
    print(f"probing {a.port} at {a.baud} baud\n")

    checks = [
        ("AT",            "is the module alive?"),
        ("AT+VER?",       "firmware version"),
        ("AT+ADDRESS?",   "this node's address"),
        ("AT+NETWORKID?", "network id (both ends must match)"),
        ("AT+BAND?",      "frequency in Hz"),
        ("AT+PARAMETER?", "spreading factor, bandwidth, coding rate, preamble"),
        ("AT+CRFOP?",     "transmit power"),
    ]
    alive = False
    for command, why in checks:
        replies = at(ser, command)
        shown = " | ".join(replies) if replies else "(no reply)"
        print(f"  {command:<15} {shown}")
        print(f"  {'':<15} ^ {why}")
        if replies:
            alive = True
    ser.close()

    print()
    if not alive:
        print("NOTHING REPLIED. In likelihood order:")
        print("  1. Wrong COM port — run: py scripts/fpga_diag.py   (it lists ports)")
        print("  2. Wrong baud — the RYLR998 default is 115200; try --baud 9600")
        print("  3. TX/RX crossed — the module's TX goes to the adapter's RX")
        print("  4. Not powered — the RYLR998 needs 3.3V, NOT 5V")
        return 1

    print("The module answered. Before sending anything, confirm on BOTH modules:")
    print("  - NETWORKID is identical")
    print("  - BAND is identical, and legal where you are")
    print("    (India: 865-867 MHz. EU: 868. US: 915. Check before transmitting.)")
    print("  - ADDRESS differs between the two")
    return 0


def cmd_config(a):
    ser = open_port(a.port, a.baud)
    print(f"configuring {a.port}\n")
    for command in (f"AT+NETWORKID={a.network}",
                    f"AT+ADDRESS={a.address}",
                    f"AT+BAND={a.band}"):
        replies = at(ser, command)
        ok = any("+OK" in r for r in replies)
        print(f"  {command:<28} {' | '.join(replies) or '(no reply)'}  {'OK' if ok else '<-- NOT ACKNOWLEDGED'}")
    print("\nreading back what actually took effect:")
    for command in ("AT+NETWORKID?", "AT+ADDRESS?", "AT+BAND?"):
        print(f"  {command:<15} {' | '.join(at(ser, command)) or '(no reply)'}")
    ser.close()
    print("\nRead-back is the point: a command that returns +OK has been accepted,")
    print("not necessarily applied. Only the second block above is evidence.")
    return 0


def _load_block(path: Path) -> bytes:
    """Accept either a mine-mode JSON record or a raw .hex file.

    THE JSON PATH WAS BROKEN UNTIL 2026-09-06 and it took first contact with
    real hardware to notice. It read a `raw_block_hex` key that the mining
    pipeline has never written: finalize.json carries `raw_block_bytes` (a byte
    COUNT, not the bytes) and `raw_block_sha256`. Sending a mined block would
    have died on KeyError. No test covered this path, because the driver had
    never been run against hardware and the failure needed a real file.

    The block itself lives in reports/mined-block.hex. Rather than reading a hex
    string out of the JSON, this resolves that file and CHECKS IT AGAINST THE
    DIGEST THE JSON CARRIES -- which is strictly better than the original design
    would have been, because the loader now verifies what it loaded instead of
    trusting it.
    """
    if path.suffix != ".json":
        return bytes.fromhex(path.read_text().split()[0].strip())

    rec = json.loads(path.read_text())
    if "raw_block_hex" in rec:
        return bytes.fromhex(rec["raw_block_hex"])

    want = rec.get("raw_block_sha256")
    if not want:
        raise SystemExit(
            f"{path} carries neither raw_block_hex nor raw_block_sha256; "
            "pass the .hex file directly instead")

    candidates = [path.with_suffix(".hex"),
                  path.parent / "mined-block.hex",
                  ROOT / "reports" / "mined-block.hex"]
    for hexfile in candidates:
        if not hexfile.exists():
            continue
        raw = bytes.fromhex(hexfile.read_text().split()[0].strip())
        got = hashlib.sha256(raw).hexdigest()
        if got == want:
            return raw
        raise SystemExit(
            f"{hexfile} does not match the digest in {path}. "
            f"json says {want}, file is {got}. "
            "Refusing to transmit a block that is not the one the record "
            "describes.")
    raise SystemExit(
        f"{path} references a block by digest but no matching .hex was found in "
        + ", ".join(str(c) for c in candidates))


def cmd_send(a):
    raw = _load_block(Path(a.block))
    frames = fragment(raw, mtu=LORA_MTU)
    h = block_hash(raw[:80])

    print(f"block   {h}")
    print(f"        {len(raw)} bytes -> {len(frames)} fragments "
          f"of at most {LORA_MTU} ({LORA_MTU - HEADER_LEN} payload)")
    print(f"        {a.repeat} pass(es), no back-channel and no retransmission "
          f"negotiation\n")

    ser = open_port(a.port, a.baud)
    sent = 0
    for rnd in range(a.repeat):
        for i, f in enumerate(frames):
            payload = f.hex().upper()
            if len(payload) > RYLR_MAX_ASCII:
                raise SystemExit(f"fragment {i} is {len(payload)} ASCII chars, "
                                 f"over the module's {RYLR_MAX_ASCII} limit")
            replies = at(ser, f"AT+SEND={a.to},{len(payload)},{payload}", wait=a.gap)
            ok = any("+OK" in r for r in replies)
            sent += 1
            print(f"  pass {rnd+1}/{a.repeat}  fragment {i+1}/{len(frames)}  "
                  f"{len(payload)} chars  {'OK' if ok else ' | '.join(replies) or 'NO REPLY'}")
            time.sleep(a.gap)
    ser.close()

    print(f"\n{sent} transmission(s) attempted.")
    print("A '+OK' means the module accepted the command for transmission. It is")
    print("NOT evidence that anything was received -- there is no back-channel by")
    print("design. Only the receiving end can tell you whether this worked.")
    return 0


def appears_isolated(probes: list, dns: dict) -> bool:
    """No probe reached anything AND DNS did not resolve.

    Both conditions, not either. A host with a working resolver but no route is
    not isolated, and a host that reaches an address while DNS is broken is not
    isolated either -- each on its own is a symptom of a misconfiguration rather
    than of an air gap.
    """
    return not any(p["reachable"] for p in probes) and not dns["resolved"]


def _write_json(path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2) + chr(10), encoding="utf-8",
                    newline=chr(10))


def _network_snapshot(label: str) -> dict:
    """Record whether this host can reach anything, right now.

    WHY THE RECEIVER ATTESTS TO ITS OWN ISOLATION

    Experiment 1 on 2026-09-06 moved a block between two machines and rested its
    central claim on the receiver having been air-gapped. The operator captured
    ipconfig and a failed ping by hand before the run -- but there was no capture
    between then and the block's arrival, leaving a three-minute window after the
    block existed in which a reconnected machine could in principle have fetched
    it from the chain instead of the air.

    Nothing suggested it had. But the experiment was designed to make that
    objection IMPOSSIBLE rather than merely implausible, and a gap that depends
    on someone remembering to run a command at the right moment is not a design,
    it is a habit. So the receiver now records this itself, at the start and end
    of every session, into the same directory the blocks land in.

    The programmatic probes are the evidence; the OS command output is included
    verbatim because that is what a human reads, and because a reader should be
    able to see the machine's own account rather than only this script's summary.
    """
    probes = []
    for host, port in (("1.1.1.1", 53), ("8.8.8.8", 53), ("9.9.9.9", 53)):
        t0 = time.time()
        try:
            socket.create_connection((host, port), timeout=3).close()
            probes.append({"target": f"{host}:{port}", "reachable": True,
                           "seconds": round(time.time() - t0, 3)})
        except Exception as e:
            probes.append({"target": f"{host}:{port}", "reachable": False,
                           "error": f"{type(e).__name__}: {e}"})
    try:
        resolved = socket.gethostbyname("example.com")
        dns = {"resolved": True, "answer": resolved}
    except Exception as e:
        dns = {"resolved": False, "error": f"{type(e).__name__}: {e}"}

    raw = {}
    for name, cmd in (("ipconfig", ["ipconfig", "/all"]),
                      ("route", ["route", "print", "0.0.0.0"])):
        try:
            raw[name] = subprocess.run(cmd, capture_output=True, text=True,
                                       timeout=20).stdout
        except Exception as e:
            raw[name] = f"({type(e).__name__}: {e})"

    isolated = appears_isolated(probes, dns)
    return {
        "label": label,
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "local": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "hostname": socket.gethostname(),
        "outbound_probes": probes,
        "dns": dns,
        "appears_isolated": isolated,
        "caveat": ("appears_isolated means three well-known resolvers were "
                   "unreachable and DNS did not resolve. That is strong evidence "
                   "of no route out, not proof: a host could still reach a local "
                   "peer, or be firewalled selectively. It is a machine-checked "
                   "observation, which is what the hand-run version was missing."),
        "os_reported": raw,
    }


def cmd_receive(a):
    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)

    start_state = _network_snapshot("session start")
    _write_json(outdir / "network-state-start.json", start_state)
    print(f"network at session start: "
          f"{'NO ROUTE OUT' if start_state['appears_isolated'] else 'REACHABLE'}"
          f"  -> {outdir / 'network-state-start.json'}")

    ser = open_port(a.port, a.baud)
    asm = Reassembler()

    print(f"listening on {a.port}, writing valid blocks to {outdir}")
    print("proof-of-work is checked locally on every reassembled block; anything")
    print("that fails is dropped and the fragment set stays open.")
    print("Ctrl+C to stop.\n")

    deadline = time.time() + a.seconds if a.seconds else None
    heard = accepted = 0
    buf = b""
    try:
        while deadline is None or time.time() < deadline:
            chunk = ser.read(ser.in_waiting or 1)
            if not chunk:
                continue
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                text = line.strip().decode("ascii", errors="replace")
                if not text.startswith("+RCV="):
                    if text:
                        print(f"  [module] {text}")
                    continue
                # +RCV=<address>,<length>,<data>,<RSSI>,<SNR>
                parts = text[5:].split(",")
                if len(parts) < 5:
                    print(f"  malformed +RCV: {text}")
                    continue
                addr, _length, data, rssi, snr = parts[0], parts[1], parts[2], parts[-2], parts[-1]
                heard += 1
                try:
                    packet = bytes.fromhex(data)
                except ValueError:
                    print(f"  from {addr}: not hex, ignoring ({len(data)} chars)")
                    continue
                print(f"  from {addr}: {len(packet)}B  RSSI {rssi} SNR {snr}", end="")
                block = asm.feed(packet, validate=pow_valid)
                if block is None:
                    print(f"   pending={asm.pending()}")
                    continue
                h = block_hash(block[:80])
                accepted += 1
                path = outdir / f"radio-block-{h[:16]}.hex"
                path.write_text(block.hex() + "\n", newline="\n")
                print(f"\n\n  *** BLOCK RECEIVED AND PROOF-OF-WORK VALID ***")
                print(f"  {h}")
                print(f"  {len(block)} bytes -> {path}\n")
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        ser.close()

    end_state = _network_snapshot("session end")
    _write_json(outdir / "network-state-end.json", end_state)

    # Both ends of the session, so the window between them is bounded by
    # machine-checked observations rather than by anyone recollection.
    iso_a = start_state["appears_isolated"]
    iso_b = end_state["appears_isolated"]
    if iso_a and iso_b:
        print("network: NO ROUTE OUT at session start AND end. Anything that arrived")
        print("         during this session did not arrive over the network.")
    elif iso_a or iso_b:
        print(f"network: ISOLATION CHANGED -- isolated at start {iso_a}, at end {iso_b}.")
        print("         A block received here cannot be attributed to the radio on")
        print("         this evidence alone. See network-state-*.json.")
    else:
        print("network: reachable at both ends. This session shows the radio works,")
        print("         not that the radio was the only channel available.")

    print(f"\nfragments heard: {heard}   valid blocks: {accepted}")
    if heard and not accepted:
        print("Fragments arrived but nothing reassembled into a valid block.")
        print("Either a fragment was lost (repeat the send: --repeat 3), or the")
        print("two ends disagree about NETWORKID/BAND and you are hearing noise.")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="mode", required=True)
    for name, fn in (("probe", cmd_probe), ("config", cmd_config),
                     ("send", cmd_send), ("receive", cmd_receive)):
        s = sub.add_parser(name)
        s.add_argument("--port", required=True)
        s.add_argument("--baud", type=int, default=115200)
        if name == "config":
            s.add_argument("--address", type=int, required=True)
            s.add_argument("--network", type=int, default=18)
            s.add_argument("--band", type=int, default=865000000,
                           help="Hz. India 865-867 MHz, EU 868, US 915. Your "
                                "responsibility to pick a legal one.")
        if name == "send":
            s.add_argument("--block", required=True)
            s.add_argument("--to", type=int, default=BROADCAST)
            s.add_argument("--repeat", type=int, default=3,
                           help="whole-transmission repeats; redundancy is achieved "
                                "by repetition because there is no back-channel")
            s.add_argument("--gap", type=float, default=0.6,
                           help="seconds between fragments (airtime + duty cycle)")
        if name == "receive":
            s.add_argument("--out", default="live/radio-received")
            s.add_argument("--seconds", type=float, default=0,
                           help="0 = listen until Ctrl+C")
        s.set_defaults(func=fn)
    a = p.parse_args()
    sys.exit(a.func(a))


if __name__ == "__main__":
    main()
