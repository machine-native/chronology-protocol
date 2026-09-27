# SPDX-License-Identifier: Apache-2.0
"""The astrolabe reproduction check keeps its contract without the engine present.

The engine is a separate and currently private repository, so this suite cannot
assume it. What it *can* pin is the part that matters to a reader who does not
have it: that the script reports INDETERMINATE rather than FAIL, and exits 2
rather than 1.

That distinction is the whole point. Reporting "could not check" as "checked and
failed" would tell a stranger the prediction is wrong when nothing about it was
examined -- the most serious defect outside review has found in this project.
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reproduce_astrolabe_expectation.py"
EXPECTATION = ROOT / "live" / "anchor-evidence" / "astrolabe-expectation.json"


def _run(env_engine: str):
    import os
    env = dict(os.environ, ASTROLABE_ENGINE=env_engine)
    return subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=300)


def test_script_is_present_and_executable():
    assert SCRIPT.is_file(), "the astrolabe reproduction script is missing"


def test_absent_engine_is_indeterminate_not_failure(tmp_path):
    """No engine must mean 'unchecked', never 'wrong'."""
    r = _run(str(tmp_path / "no-such-engine"))
    assert r.returncode == 2, (
        "a missing engine must exit 2 (indeterminate), not "
        f"{r.returncode}\n{r.stdout}\n{r.stderr}")
    assert "INDETERMINATE" in r.stdout
    assert "FAIL" not in r.stdout
    # and it must say what to do about it
    assert "ASTROLABE_ENGINE" in r.stdout


def test_expectation_file_is_well_formed():
    """Whatever the engine says, the recorded file must be readable and labelled."""
    d = json.loads(EXPECTATION.read_text(encoding="utf-8"))
    assert d["label"] == "EXPECTATION_NOT_EVIDENCE", (
        "the astrolabe prediction must stay labelled as an expectation; it is a "
        "model's output, not an observation of the sky")
    assert d["instant_utc"].endswith("Z")
    assert d["grahas"], "no grahas recorded"
    for g in d["grahas"]:
        assert "tropical_lon_deg" in g and "ecliptic_lat_deg" in g
        # a tolerance must be stated somewhere, or 'agreement' has no meaning
        assert "tolerance_arcsec" in g or "tolerance_arcsec" in d.get("provider_floor", {})
    assert "engine" in d, "the expectation must name the engine build it came from"
