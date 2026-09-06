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
state in `/var/lib/bitcoin-node`, and sets `ufw` to allow **SSH and 18026/tcp
only**.

**Note the ufw rule.** If satledger serves anything on another port, that rule
will close it. Check what the machine is currently exposing before running this,
and re-add any port that must stay open:

```bash
sudo ufw status numbered      # BEFORE
# ... provision ...
sudo ufw status numbered      # AFTER -- compare, re-add what you need
```

## provision.sh alone leaves the node empty — add a peer

**This step is not in `provision.sh` and the seed does not work without it.**

The script stands a node up as *the* seed, not as a second one joining a network
that already exists. It writes no outbound peer, so the node comes up at
**height 0** with only the genesis it minted itself — listening, but with nothing
to serve. A cross-check against it times out, which looks like a network fault
and is not one.

Found doing exactly this on 2026-09-06.

```bash
sed -i 's|--advertise ${ADVERTISE_IP}|--advertise ${ADVERTISE_IP} --connect bitcoin.bitcoin-lab.org:18026|'     /etc/systemd/system/bitcoin-node.service
systemctl daemon-reload && systemctl restart bitcoin-node
journalctl -u bitcoin-node -n 10 --no-pager
```

Expect `connected out to bitcoin.bitcoin-lab.org:18026`, and then a second
`connected out to` line for a peer it learned by gossip. `blocks.dat` grows from
274 bytes — one block — to the size of the chain.

`--connect` is repeatable, so a third seed should name **both** existing seeds
rather than depending on one.

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

## DNS

Give it a name so the IP is not the interface:

    seed2.bitcoin-lab.org   A   <netcup-ipv4>

Then re-run `check_seeds.py` against the **name**, not the address — that is what
a stranger will use, so that is what should be tested.

## When it is done

Record in `governance-adr` under D2: the provider, the jurisdiction, the date,
and the `check_seeds.py` output showing agreement. Two of three.

The third seed should be on a **third provider in a third jurisdiction**, and
ADR-0004 asks for at least one outside the operator's own — which is the part
that starts to buy something more than availability.
