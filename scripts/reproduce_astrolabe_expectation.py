#!/usr/bin/env python3
"""Re-derive the astrolabe expectation from the engine, instead of trusting it.

WHY THIS EXISTS

`live/anchor-evidence/astrolabe-expectation.json` carries the open-astrolabe
engine's prediction for the epoch-2 capture instant, labelled
EXPECTATION_NOT_EVIDENCE. Until now it was a *recorded* value: produced once by
running the engine somewhere else, pasted in, and never checked again.

Every other expectation in this record is recomputed. `ctp.sandwich.era_expectation`
derives the IAU-2000 Earth Rotation Angle in-process, and the verifier asserts the
bundle matches it. The astrolabe prediction was the one that did not -- which is the
unfinished half of G2b in ADR-0001: the optical observation was made, the engine
integration was not.

This closes that half. It re-derives the prediction from the pinned engine and
compares it against the recorded file, within the tolerance the engine declared.

THREE OUTCOMES, NEVER TWO

    PASS            re-derived, and it agrees inside the declared tolerance
    FAIL            re-derived, and it does not
    INDETERMINATE   could not re-derive -- no engine, no node, no expectation

The third is not a soft failure. The engine lives in a separate and currently
private repository; a reader without it has not checked this, and must not be
told that they have.

    ASTROLABE_ENGINE=<path>   # defaults to a sibling workspace checkout

Exit codes:  0 agrees - 1 disagrees - 2 could not be checked
"""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTATION = ROOT / "live" / "anchor-evidence" / "astrolabe-expectation.json"
ENGINE = Path(os.environ.get(
    "ASTROLABE_ENGINE",
    ROOT.parent.parent / "vscode_workspace_jyotish-astrolabe" / "open-astrolabe-engine"))

PASS, FAIL, INDET = "PASS", "FAIL", "INDETERMINATE"

JS = """
Promise.all([import('astronomy-engine'),
             import('./packages/core/dist/index.js'),
             import('./packages/ephemeris-analytic/dist/index.js')])
 .then(([A, core, eph]) => {
   const Astronomy = A.default ?? A;
   const iso = process.argv[1];
   const grahas = JSON.parse(process.argv[2]);
   const ts = core.buildTimeState({ utcIso: iso, timezone: 'UTC' });
   const dt = core.deltaTSeconds(core.decimalYearFromIsoUtc(iso));
   const jdTt = ts.julianDayUtc + dt.seconds / 86400;
   const t = Astronomy.MakeTime(new Date(iso));
   const out = {
     software_version: core.SOFTWARE_VERSION,
     jd_ut: ts.julianDayUtc,
     delta_t_seconds: dt.seconds,
     delta_t_model: dt.model,
     jd_tt: jdTt,
     gast_deg: core.gastDeg(ts.julianDayUtc, jdTt),
     grahas: {},
   };
   for (const g of grahas) {
     const p = eph.tropicalPositionOfDate(g, t);
     out.grahas[g] = { lon: p.lonDeg, lat: p.latDeg };
   }
   process.stdout.write(JSON.stringify(out));
 })
 .catch(e => { process.stderr.write(String((e && e.message) || e)); process.exit(3); });
"""


def indeterminate(reason: str) -> int:
    print("\n  " + INDET)
    print("  " + reason + "\n")
    print("  Nothing was contradicted. The prediction in the record is unchecked by")
    print("  this run, which is not the same as checked and wrong.\n")
    return 2


def main() -> int:
    if not EXPECTATION.is_file():
        return indeterminate(str(EXPECTATION) + " is not in this checkout")
    exp = json.loads(EXPECTATION.read_text(encoding="utf-8"))

    if not (ENGINE / "packages" / "core" / "dist" / "index.js").is_file():
        return indeterminate(
            "no built open-astrolabe engine at " + str(ENGINE) + ".\n"
            "  Set ASTROLABE_ENGINE to a built checkout. The engine is a separate\n"
            "  repository and is deliberately not vendored here.")

    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return indeterminate("node is not on PATH; the engine cannot be run")

    # The expectation names the commit it came from. A different one is still worth
    # running; it is just not the same claim, so say so rather than compare silently.
    recorded_engine = exp.get("engine", "")
    head = subprocess.run(["git", "-C", str(ENGINE), "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    commit_note = ""
    if head and head not in recorded_engine:
        commit_note = ("engine HEAD is " + head + "; the expectation was produced at "
                       + repr(recorded_engine))

    names = [g["graha"] for g in exp.get("grahas", [])]
    # Run with --input-type=module -e rather than from a temporary file. An ESM
    # file resolves its bare imports relative to ITSELF, so a script in the system
    # temp directory cannot find the engine's own node_modules however cwd is set.
    # With -e the resolution base is the working directory, which is the engine.
    r = subprocess.run(["node", "--input-type=module", "-e", JS,
                        exp["instant_utc"], json.dumps(names)],
                       cwd=ENGINE, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        return indeterminate("the engine could not be run: " + r.stderr.strip()[:300])
    got = json.loads(r.stdout)

    print("\nastrolabe expectation, re-derived  (" + exp["instant_utc"] + ")\n")
    if commit_note:
        print("  NOTE  " + commit_note + "\n")

    rows = []
    worst = 0.0
    failed = []

    floor = float(exp.get("provider_floor", {}).get("tolerance_arcsec", 10))
    for g in exp.get("grahas", []):
        name = g["graha"]
        tol = float(g.get("tolerance_arcsec", floor))
        for field, key in (("tropical_lon_deg", "lon"), ("ecliptic_lat_deg", "lat")):
            recorded = float(g[field])
            derived = float(got["grahas"][name][key])
            d_arcsec = (derived - recorded) * 3600.0
            worst = max(worst, abs(d_arcsec))
            ok = abs(d_arcsec) <= tol
            if not ok:
                failed.append(name + " " + field + ": " + format(d_arcsec, "+.4f")
                              + " arcsec exceeds " + format(tol, "g"))
            rows.append((name + " " + field, derived, d_arcsec, tol, ok))

    for label, derived, d, tol, ok in rows:
        mark = "ok  " if ok else "FAIL"
        print("  {} {:<28} {:>20.10f}   d {:+9.5f}\"  (tolerance {:g}\")".format(
            mark, label, derived, d, tol))

    print()
    dt_same = got["delta_t_model"] == exp["time_scales"].get("delta_t_source")
    d_dt = got["delta_t_seconds"] - float(exp["time_scales"]["delta_t_seconds"])
    print("  dT model   " + str(got["delta_t_model"])
          + ("  (matches the record)" if dt_same else "  DIFFERS from the record"))
    print("  dT value   {:.9f} s   d {:+.6f} s against the record".format(
        got["delta_t_seconds"], d_dt))
    print("  engine     v" + str(got["software_version"]))

    if failed:
        print("\n  " + FAIL)
        for f in failed:
            print("    " + f)
        print("\n  The recorded prediction does not re-derive. That is a finding about")
        print("  this record, and should be reported rather than smoothed over.\n")
        return 1

    print("\n  " + PASS + " -- every value re-derives inside the tolerance the engine declared.")
    print("  Worst disagreement: {:.5f} arcsec.".format(worst))
    print("\n  This makes the prediction reproducible rather than asserted. It stays")
    print("  EXPECTATION_NOT_EVIDENCE: a model agreeing with itself says nothing about")
    print("  the sky. What it rules out is the number having been recorded wrongly.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
