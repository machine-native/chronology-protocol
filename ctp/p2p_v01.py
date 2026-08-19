"""Minimal Bitcoin v0.1-era P2P framing for the OBL derivative laboratory chain.

This module deliberately implements only the small surface needed to submit an already-mined block.
Wire format: magic[4] || command[12] || payload_size[4 LE] || payload.  No message checksum.
"""
from __future__ import annotations
import ipaddress, socket, struct, time

DEFAULT_MAGIC = bytes.fromhex("f00ba726")
DEFAULT_PORT = 18026
DEFAULT_PROTOCOL_VERSION = 101
NODE_NETWORK = 1

class P2PError(RuntimeError):
    pass

def build_message(command: str, payload: bytes, magic: bytes = DEFAULT_MAGIC) -> bytes:
    c = command.encode("ascii")
    if not (1 <= len(c) <= 12):
        raise ValueError("command must be 1..12 ASCII bytes")
    if len(magic) != 4:
        raise ValueError("magic must be 4 bytes")
    return magic + c.ljust(12, b"\x00") + struct.pack("<I", len(payload)) + payload

def encode_address(ip: str, port: int, services: int = NODE_NETWORK) -> bytes:
    addr = ipaddress.ip_address(ip)
    if addr.version == 4:
        raw = b"\x00"*10 + b"\xff\xff" + addr.packed
    else:
        raw = addr.packed
    return struct.pack("<Q", services) + raw + struct.pack(">H", port)

def version_payload(
    peer_ip: str,
    peer_port: int,
    *,
    protocol_version: int = DEFAULT_PROTOCOL_VERSION,
    services: int = NODE_NETWORK,
    timestamp: int | None = None,
) -> bytes:
    # v0.1-era payload: version + services + nTime + addrMe.
    if timestamp is None:
        timestamp = int(time.time())
    return (
        struct.pack("<iQq", protocol_version, services, timestamp)
        + encode_address(peer_ip, peer_port, services)
    )

def recv_message(sock: socket.socket, magic: bytes = DEFAULT_MAGIC):
    def exact(n):
        b = bytearray()
        while len(b) < n:
            c = sock.recv(n-len(b))
            if not c:
                raise EOFError
            b += c
        return bytes(b)
    header = exact(20)
    if header[:4] != magic:
        raise P2PError(f"unexpected magic {header[:4].hex()}")
    command = header[4:16].split(b"\x00",1)[0].decode("ascii", errors="replace")
    size = struct.unpack("<I", header[16:20])[0]
    if size > 32*1024*1024:
        raise P2PError("refusing oversized message")
    return command, exact(size)

def submit_block(
    host: str,
    port: int,
    raw_block: bytes,
    *,
    magic: bytes = DEFAULT_MAGIC,
    protocol_version: int = DEFAULT_PROTOCOL_VERSION,
    timeout: float = 5.0,
):
    """Send a mined raw block after a v0.1-style version exchange.

    A successful socket send is NOT itself proof the node accepted the block.
    Callers must preserve independent node/chain evidence.
    """
    peer_ip = socket.gethostbyname(host)
    events=[]
    with socket.create_connection((host, port), timeout=timeout) as s:
        s.settimeout(timeout)
        # Send our version immediately. v0.1 has no verack requirement.
        vp = version_payload(peer_ip, port, protocol_version=protocol_version)
        s.sendall(build_message("version", vp, magic))
        events.append({"event":"VERSION_SENT","protocol_version":protocol_version})

        # Try to consume peer's version if it arrives, but do not make a later verack mandatory.
        try:
            command, payload = recv_message(s, magic)
            events.append({"event":"MESSAGE_RECEIVED","command":command,"bytes":len(payload)})
        except socket.timeout:
            events.append({"event":"VERSION_RESPONSE_TIMEOUT"})
        except EOFError:
            raise P2PError("peer closed connection during handshake")

        s.sendall(build_message("block", raw_block, magic))
        events.append({"event":"BLOCK_SENT","bytes":len(raw_block)})

        # Collect any immediate response for audit only.
        deadline=time.time()+timeout
        while time.time()<deadline:
            s.settimeout(max(0.05,deadline-time.time()))
            try:
                command,payload=recv_message(s,magic)
                events.append({"event":"MESSAGE_RECEIVED","command":command,"bytes":len(payload)})
            except socket.timeout:
                break
            except EOFError:
                events.append({"event":"PEER_CLOSED"})
                break
    return events
