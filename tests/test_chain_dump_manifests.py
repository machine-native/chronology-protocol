# SPDX-License-Identifier: Apache-2.0
"""The two manifests disagree about the chain dump, and that is deliberate.

`live/chain-blocks.hex` is named in both:

  * `MANIFEST.sha256` at the repository root records the file **as it is now**, so
    a clone verifies. The dump is refreshed as the chain grows -- seven times since
    the first capture -- and this line moves with it.

  * `live/MANIFEST-live.sha256` records it **as captured on 2026-08-19** and does
    not move. A capture-time manifest regenerated after the fact stops being a
    record of the capture, which is the whole reason it exists.

Someone tidying up will eventually notice the two digests differ and "fix" it.
These tests exist so that tidying fails loudly instead of silently destroying the
capture record.
"""
from __future__ import annotations
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "live"))

REL = "live/chain-blocks.hex"
ROOT_MANIFEST = ROOT / "MANIFEST.sha256"
LIVE_MANIFEST = ROOT / "live" / "MANIFEST-live.sha256"

# The digest MANIFEST-live.sha256 has recorded since 2026-08-19. Pinned here so a
# regeneration of that file is caught by this suite rather than by a reader years
# from now wondering why the capture record tracks the present.
CAPTURE_TIME_DIGEST = "2572fac346d8f289d7b84321e64d3ec14b90ed25fc207970a64db5ce1518c916"


def _lines_for(manifest: Path):
    out = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        if name.lstrip("*") == REL:
            out.append(digest)
    return out


def test_root_manifest_names_the_dump_exactly_once():
    """restamp_manifest() refuses to act unless this holds."""
    assert len(_lines_for(ROOT_MANIFEST)) == 1


def test_capture_time_manifest_still_records_the_capture():
    found = _lines_for(LIVE_MANIFEST)
    assert found == [CAPTURE_TIME_DIGEST], (
        "live/MANIFEST-live.sha256 no longer records the 2026-08-19 capture of "
        f"{REL}. If it was regenerated, that destroyed a record of what was "
        "captured and replaced it with a statement about the present, which the "
        "root manifest already makes.")


def test_the_two_manifests_are_meant_to_disagree():
    """Not a bug. The dump has moved on; the capture has not."""
    now = _lines_for(ROOT_MANIFEST)[0]
    assert now != CAPTURE_TIME_DIGEST, (
        "the dump currently matches its 2026-08-19 capture digest. That is "
        "possible but surprising after seven refreshes -- check that the root "
        "manifest was not overwritten with the capture-time value.")


def test_root_manifest_matches_the_file_on_disk():
    """What a clone checks, and what --refresh restamps."""
    recorded = _lines_for(ROOT_MANIFEST)[0]
    actual = hashlib.sha256((ROOT / REL).read_bytes()).hexdigest()
    assert recorded == actual, (
        "MANIFEST.sha256 is stale for the chain dump. If this followed a "
        "--refresh, restamp_manifest() did not run; verify_all.py will report "
        "FAIL on the manifest check and a reader will think the evidence broke.")


def test_restamp_is_a_noop_when_already_correct():
    """It must not rewrite the manifest, and must not touch the capture record."""
    from capture_retarget import restamp_manifest

    before_root = ROOT_MANIFEST.read_bytes()
    before_live = LIVE_MANIFEST.read_bytes()
    restamp_manifest()
    assert ROOT_MANIFEST.read_bytes() == before_root, (
        "restamp_manifest rewrote the manifest when nothing had changed")
    assert LIVE_MANIFEST.read_bytes() == before_live, (
        "restamp_manifest touched the capture-time manifest, which it must never do")
