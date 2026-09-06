# D2 — adding a second seed on netcup

Today **one** DigitalOcean droplet is the only reachable entry point to the anchor
chain. If it goes away — provider action, a lapsed payment, a legal order, a dead
disk — the chain becomes unreachable to strangers even though every byte survives.

A netcup VPS is already paid for a year. That makes this account-and-DNS work
rather than engineering: `provision.sh` already exists, is idempotent, and lists
everything it does.

## What this buys, and what it does not

**Buys:** availability. Two providers, two jurisdictions (DigitalOcean and
netcup, a German host), two failure domains. A stranger can still reach the chain
when one disappears.

**Does not buy:** operator independence. Both seeds would still be **ours**. A
reader who distrusts this project gains nothing from a second machine the same
project runs. ADR-0004 says this plainly and so should any announcement:
*availability insurance, described as exactly that.*

**Does not buy:** anything about evidence quality. The evidence is already
self-authenticating; a seed is a way to fetch it, not a reason to believe it.

The target in ADR-0004 is **three** seeds on three providers in three
jurisdictions, at least one outside the operator's own. This is the second.

## Before touching the VPS

That machine already runs satroot/satledger. Two checks first:

```bash
sudo ss -lntp | grep -E ':18026|:22'     # 18026 must be free
df -h /            # the chain is ~116 KB raw; disk is not the constraint
free -m            # nor is memory, but confirm there is headroom
```

If 18026 is taken, stop and say so — the port is part of the protocol identity
(magic `f00ba726`, deliberately not mainnet's 8333) and changing it means the
seed is not interchangeable with the first.

## Provision

```bash
ssh root@<netcup-ipv4>
curl -fsSL https://raw.githubusercontent.com/original-bitcoin-laboratory/genesis/main/derivatives/bitcoin/deploy/provision.sh \
  | bash -s -- <netcup-ipv4>
```

Pass the **public IPv4**, because that is the address peers dial back on. The
script is idempotent, so a re-run is safe if anything is interrupted.

What it does, all of it: installs python3/git/ufw/build-essential, clones the
laboratory genesis to `/opt/obl`, runs the node as a systemd `DynamicUser` with
state in `/var/lib/bitcoin-node`, verifies the genesis meets difficulty-1 before
agreeing to serve it, and adds `ufw` rules for SSH and 18026/tcp.

**It ADDS firewall rules; it does not reset them.** The three lines are
`ufw allow OpenSSH`, `ufw allow 18026/tcp`, `ufw --force enable` — so existing
rules survive. An earlier draft of this document said it allowed "SSH and 18026
only", which was wrong and would have caused someone to prepare for damage that
does not happen.

The case that *would* bite: if `ufw` is currently **inactive** and something is
served without it, `--force enable` applies a default-deny policy and closes
whatever has no rule. So check first, and add rules for anything that must
survive **before** provisioning:

```bash
sudo ufw status verbose          # active already? what is allowed?
sudo ufw allow 80/tcp            # only if needed and not already present
sudo ufw allow 443/tcp
```

On 2026-09-06 this machine already had `ufw` active with 22, 80 and 443 allowed
on both v4 and v6, so provisioning added 18026 and changed nothing else. Caddy
kept serving throughout — verified afterwards: port 80 returns 308, port 443
returns 400 to a curl without SNI. Both alive.

## provision.sh alone leaves the node empty — add a peer

**This step is not in `provision.sh` and the seed does not work without it.**

The script stands a node up as *the* seed, not as a second one joining a network
that already exists. It writes no outbound peer, so the node comes up at
**height 0** with only the genesis it minted itself — listening, but with nothing
to serve. A cross-check against it times out, which looks like a network fault
and is not one.

Found doing exactly this on 2026-09-06.

**Use a drop-in, not `sed` on the unit.** An earlier version of this document
edited `bitcoin-node.service` directly. That works until the next `provision.sh`
run, which is idempotent and **rewrites the unit** — silently discarding the
edit. The node then restarts at height 0 with only its self-minted genesis:
listening, healthy-looking, serving nothing.

```bash
mkdir -p /etc/systemd/system/bitcoin-node.service.d
cat > /etc/systemd/system/bitcoin-node.service.d/override.conf <<'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/python3 -m netnode --chain bitcoin --datadir /var/lib/bitcoin-node --listen [::]:18026 --advertise ${ADVERTISE_IP} --connect <EXISTING-SEED-IPV4>:18026
EOF
systemctl daemon-reload && systemctl restart bitcoin-node
journalctl -u bitcoin-node -n 10 --no-pager
```

The empty `ExecStart=` is required: it clears the unit's value before the
replacement, and without it systemd rejects the second assignment.

Expect `connected out to <seed>:18026`, and then a second `connected out to`
line for a peer it learned by gossip. `blocks.dat` grows from 274 bytes — one
block — to the size of the chain.

**Name the peer by ADDRESS, not by the round-robin name.** Once
`bitcoin.bitcoin-lab.org` carries an A record for every seed, a node that dials
that name can resolve to **itself** — the log says
`not dialling bitcoin.bitcoin-lab.org:18026 — that is us`. On 2026-09-07 the
netcup seed did exactly this and recovered only because the resolver also
returned the other A record in the same answer. A resolution returning self
alone leaves the node with **no outbound peer at all**, sitting at whatever
height it already holds and looking entirely healthy.

`--connect` is repeatable. Lead with the explicit address and keep the name as a
secondary; a third seed should name **both** existing seeds by address.

## Verify it is really serving the same chain

From this laptop, not from the VPS:

```bash
python live/check_seeds.py bitcoin.bitcoin-lab.org:18026 <netcup-ipv4>:18026
```

This does a v0.1 handshake against each, asks for blocks from the genesis
locator, and compares the advertised inventory **hash by hash**. Agreement is
decided from the block hashes themselves, not from what either node says about
itself.

It distinguishes *behind/ahead by N* from *forked at height H*. The first is
normal while a block propagates. Only the second is a fault, and only the second
should stop you.

Expected: both seeds report the same genesis
`00000000ad12f3ecd9b14e4276ac98936fb0d658f05dce95ad35d18fceee208a` and agree on
the tip within a block or two.

## DNS — mind which family the name belongs to

**Not `seed2`.** The two prefixes already in use mean different networks:

    seed.bitcoin-lab.org      port 18009    the earlier chain
                              round-robins 143.110.255.205, 178.62.236.102
    bitcoin.bitcoin-lab.org   port 18026    Bitcoin (Aug 2026)
                              168.144.27.117

This seed serves **18026**, so it belongs in the `bitcoin.` family. A `seed2`
name would file it under a prefix that means a different chain — which is the
kind of error that costs someone an hour before they check the port.

    bitcoin2.bitcoin-lab.org   A   89.58.17.204

**A second option, matching what `seed.` already does:** add the new address as
a second A record on `bitcoin.bitcoin-lab.org` so the existing name round-robins
across both. A stranger following VERIFY.md then reaches whichever is up without
knowing there are two.

The trade-off is real: DNS round-robin does not health-check, so a dead seed
means roughly half of connections fail rather than none. The laboratory's own
notes describe a health-aware resolver answering with the live set, which is the
proper fix and does not exist yet.

**Do both.** `bitcoin2` gives each seed an addressable name, which is what
`check_seeds.py` needs to compare them; the round-robin entry is what makes the
redundancy useful to someone who never reads this file.

Then re-run `check_seeds.py` against the **names**, not the addresses — that is
what a stranger will use, so that is what should be tested.

## When it is done

Record in `governance-adr` under D2: the provider, the jurisdiction, the date,
and the `check_seeds.py` output showing agreement. Two of three.

The third seed should be on a **third provider in a third jurisdiction**, and
ADR-0004 asks for at least one outside the operator's own — which is the part
that starts to buy something more than availability.


---

## IPv6 defeats the round-robin unless you do two more things

Found on 2026-09-06, after the A record was added and the round-robin appeared
to be working.

**The `AAAA` record pointed only at the first seed.** Modern resolvers prefer
IPv6 (RFC 6724), so any IPv6-capable client resolves `bitcoin.bitcoin-lab.org`,
gets the one AAAA answer, and reaches the original seed **every time**. The
IPv4 round-robin is never consulted. The redundancy looks present and is not,
for exactly the clients most likely to have modern networking.

Two fixes, both needed:

**1. Advertise both families on the node.** `netnode --advertise` takes a
comma-separated list. The provisioned unit had only the IPv4:

Put this in the **same drop-in** as `--connect`, for the same reason — a
`provision.sh` re-run writes only the IPv4:

```bash
# inside /etc/systemd/system/bitcoin-node.service.d/override.conf, [Service]
Environment=ADVERTISE_IP=<v4>,<v6>
```

```bash
systemctl daemon-reload && systemctl restart bitcoin-node
```

Without this the node listens on `[::]` but never tells peers its IPv6 address,
so gossip cannot spread it.

**2. Add the AAAA record**, alongside the existing one:

    bitcoin.bitcoin-lab.org   AAAA   <the new seed's IPv6>

Then a v6 client gets two answers and the redundancy is real in both families.

**Check it from a host that actually has IPv6.** A machine without it will
resolve AAAA fine and still fail to connect, which looks like a broken seed and
is a broken client.

---

## If the seed shares a host with anything that matters

Added 2026-09-07, after an operator review of the netcup box.

A seed is the only process on its host accepting **unauthenticated connections
from the internet**. When it is co-tenanted — the netcup machine also runs the
satledger payment API and its ed25519 signing keys, which cannot be regenerated
without orphaning every existing ledger — that asymmetry deserves ceilings.

`provision.sh` sets none: `MemoryMax=infinity`, no CPU quota. Steady state is
~15 MB, so this is not urgent, but an unbounded P2P process can starve its
neighbours under load or attack, and here the neighbour holds the keys.

In the same drop-in:

```
MemoryMax=1G
MemoryHigh=768M
CPUQuota=50%
TasksMax=256
```

1 GB is ~66× steady state, so it will not bite in normal operation.

**What is already correct and should stay that way.** `provision.sh` runs the
node under `DynamicUser=yes` with `ProtectSystem=strict` and
`NoNewPrivileges=yes`, giving it its own uid/gid and **no supplementary
groups**. Keep it that way: never root, and never in `docker` (root-equivalent)
or `systemd-journal`. State stays inside `/var/lib/bitcoin-node`.

**Verify the drop-in actually wins** rather than assuming it — the unit file
still holds the old values, so the merge is the only thing making it true:

```bash
systemctl cat bitcoin-node                    # shows the merge order
systemctl show bitcoin-node -p ExecStart --value | grep -o '\-\-connect [^ ]*'
```

## What `python3 -m netnode` actually is

Worth recording, because an operator reviewing the host could not find it
installed and the answer is not obvious.

It is **not a PyPI package.** The unit sets
`WorkingDirectory=/opt/obl/derivatives`, so `-m netnode` resolves to the local
directory `/opt/obl/derivatives/netnode` — ~5,100 lines of first-party Python
from `github.com/original-bitcoin-laboratory/genesis`. `import netnode` fails
from any other working directory.

**One third-party dependency on the running path:** `cryptography`, from the
distribution's own `python3-cryptography` package, so it patches through the OS
security channel. `bitcoinx` and `electrumsv_secp256k1` appear in
`fastverify.py` but are optional libsecp256k1 accelerators behind an
`ImportError` guard; absent, it falls back to OpenSSL. `pytest` is test-only.

**It is not pinned.** `/opt/obl` tracks `origin/main` with no tag. And that
repository is a **monorepo** holding the websites as well as the derivatives —
so a `git pull` to update a website also moves the code of an internet-facing
node. Pin to a tag and update deliberately; that coupling is a larger provenance
risk than any dependency here.
