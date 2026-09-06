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
