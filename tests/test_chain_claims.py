"""Keep VERIFY.md's documented chain output matching the actual chain.

Three separate defects found by outside reviewers were stale documentation: an
undeclared dependency, a stale test count, and a sentence describing code that
had been rewritten. This is the same class. VERIFY.md tells a verifier exactly
what the anchor scan should print, and the chain grows -- so the two drift apart
silently unless something checks.

The drift is not hypothetical. Mining height 298 added a fifth line to that
output, and a duplicate `epoch 0` at that, which reads as a defect to anyone who
had only the old list to compare against.
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ctp.bitcoin_jan09 import block_hash, parse_single_tx_block, extract_anchor_from_coinbase

CHAIN = ROOT / "live" / "chain-blocks.hex"
VERIFY = ROOT / "VERIFY.md"


def _anchors_on_chain():
    if not CHAIN.is_file():
        pytest.skip("live/chain-blocks.hex not present")
    out = []
    for i, line in enumerate(CHAIN.read_text().split()):
        raw = bytes.fromhex(line.strip())
        try:
            _, tx = parse_single_tx_block(raw)
            a = extract_anchor_from_coinbase(tx)
        except Exception:
            continue
        out.append((a["epoch"], i + 1, block_hash(raw[:80])))
    return out


def test_verify_md_lists_every_anchor_the_chain_actually_carries():
    """Every anchor-bearing block on disk must appear in VERIFY.md's expected output.

    A verifier who sees a line the document does not mention has no way to tell
    a new block from a defect, and the honest response to that ambiguity is to
    report it -- which wastes their time and ours.
    """
    doc = VERIFY.read_text(encoding="utf-8")
    missing = [
        f"epoch {e}  height {h}  {hh}"
        for e, h, hh in _anchors_on_chain()
        if hh not in doc
    ]
    assert not missing, (
        "the chain carries anchors VERIFY.md does not document:\n  "
        + "\n  ".join(missing)
        + "\nAdd them, and say what they are -- an undocumented line reads as a bug."
    )


def test_verify_md_does_not_promise_anchors_that_are_gone():
    """The reverse drift: a hash documented as expected must still be on the chain.

    Height 264 was orphaned once already by this chain's first reorganisation.
    A hash left in the document after its block leaves the chain would send a
    verifier looking for something that is not there.
    """
    on_chain = {hh for _, _, hh in _anchors_on_chain()}
    if not on_chain:
        pytest.skip("no anchors parsed")
    doc = VERIFY.read_text(encoding="utf-8")
    block = re.search(r"epoch 0  height 221.*?```", doc, re.S)
    assert block, "VERIFY.md's expected-anchor block is no longer in the known form"
    promised = re.findall(r"epoch \d+\s+height \d+\s+([0-9a-f]{64})", block.group(0))
    assert promised, "no hashes found in the expected-anchor block"
    gone = [h for h in promised if h not in on_chain]
    assert not gone, (
        "VERIFY.md promises anchors the chain no longer carries:\n  "
        + "\n  ".join(gone)
    )


def test_a_repeated_epoch_is_explained_rather_than_left_looking_like_a_bug():
    """If two blocks carry the same epoch, the document must say why.

    Height 298 was mined without --payload-hex, so it re-used the epoch-0
    payload. That is a real proof-of-work block carrying a copy of an existing
    anchor, not a second claim about epoch 0 -- a distinction a reader cannot
    make from the scan output alone.
    """
    epochs = [e for e, _, _ in _anchors_on_chain()]
    dupes = {e for e in epochs if epochs.count(e) > 1}
    if not dupes:
        pytest.skip("no repeated epochs on the chain")
    doc = VERIFY.read_text(encoding="utf-8")
    assert "is expected and is not a defect" in doc, (
        f"epoch(s) {sorted(dupes)} appear more than once on the chain, and "
        "VERIFY.md does not explain it. A reader will read a repeat as a bug."
    )
