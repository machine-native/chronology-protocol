#!/usr/bin/env python3
"""Everything a verifier would check, in one command.

VERIFY.md walks through this by hand and explains what each step proves, which
is the right document to read first. This is the same checks with no reading:
run it, get one verdict, and go back to VERIFY.md if a line needs explaining.

WHY THIS EXISTS

The one thing this record still lacks is outside verification. Every barrier
between a curious stranger and a result is a reason they close the tab, and
"run these fourteen commands and interpret each" is a barrier. This is not a
substitute for understanding what is being checked -- it is a way to find out
whether anything is broken before deciding whether to care.

THREE OUTCOMES, NEVER TWO

    PASS            checked, and it held
    FAIL            checked, and it did not
    INDETERMINATE   could not check

The third is not a softer failure. A missing OpenSSL 3.5, no network, or an
absent optional file means a question was not asked, and reporting that as FAIL
would say the evidence is bad when nothing about the evidence was examined. That
conflation was the most serious defect outside review ever found in this
project, and it is not being reintroduced in the tool built to summarise it.

Exit codes:  0 everything checked passed · 1 something failed ·
             2 nothing failed but something could not be checked
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PASS, FAIL, INDET = "PASS", "FAIL", "INDETERMINATE"

PLAIN_BUNDLES = ["evidence-bundle.cbor", "evidence-bundle-live-anchored.cbor"]
SANDWICH_BUNDLES = [
    "reality-sandwich-bundle.cbor",
    "astro-sandwich-bundle.cbor",
    "roughtime-sandwich-bundle.cbor",
    "rolling-code-sandwich-bundle.cbor",
    "satroot-binding-bundle.cbor",
    "pm-binding-bundle.cbor",
    "pm2-binding-bundle.cbor",
]


def run(cmd, timeout=600):
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           timeout=timeout)
        return r.returncode, r.stdout + r.stderr
    except FileNotFoundError as e:
        return None, f"{type(e).__name__}: {e}"
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout}s"


def check_toolchain() -> tuple[str, str]:
    """OpenSSL 3.5+ with both PQ families, or nothing PQ can be checked at all."""
    code, out = run(["openssl", "list", "-signature-algorithms"], timeout=60)
    if code is None:
        return INDET, "openssl not found on PATH; PQ signatures cannot be checked"
    have = [a for a in ("ML-DSA-87", "SLH-DSA-SHAKE-256s") if a in out]
    if len(have) == 2:
        return PASS, "ML-DSA-87 and SLH-DSA-SHAKE-256s both available"
    missing = {"ML-DSA-87", "SLH-DSA-SHAKE-256s"} - set(have)
    return INDET, (f"OpenSSL lacks {', '.join(sorted(missing))} -- needs 3.5 or "
                   "newer. Every PQ signature check below is unasked, not failed.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-network", action="store_true",
                    help="do not contact a block explorer; the attestation check "
                         "is then reported INDETERMINATE rather than skipped "
                         "silently")
    ap.add_argument("--json", metavar="PATH", default=None)
    a = ap.parse_args()

    results: list[dict] = []

    def record(name, status, detail):
        results.append({"check": name, "status": status, "detail": detail})
        mark = {PASS: "PASS ", FAIL: "FAIL ", INDET: "INDET"}[status]
        print(f"  {mark}  {name}")
        if status != PASS:
            print(f"         {detail}")

    print(f"\nchronology-protocol verify-all  ({time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})\n")

    tool_status, tool_detail = check_toolchain()
    record("toolchain: OpenSSL 3.5+ with ML-DSA-87 and SLH-DSA-SHAKE-256s",
           tool_status, tool_detail)
    pq_ok = tool_status == PASS

    code, out = run([sys.executable, "-m", "pytest", "-q"], timeout=1800)
    if code is None:
        record("test suite", INDET, out.strip()[:200])
    else:
        last = [l for l in out.strip().splitlines() if l.strip()][-1]
        record("test suite", PASS if code == 0 else FAIL, last.strip())

    for name in PLAIN_BUNDLES:
        path = Path("vectors/valid") / name
        if not (ROOT / path).exists():
            record(f"bundle {name}", INDET, "not present in this checkout")
            continue
        if not pq_ok:
            record(f"bundle {name}", INDET,
                   "skipped: the toolchain cannot check PQ signatures")
            continue
        code, out = run([sys.executable, "scripts/verify_bundle.py", str(path)])
        record(f"bundle {name}", PASS if code == 0 else FAIL,
               out.strip().splitlines()[-1] if out.strip() else "no output")

    for name in SANDWICH_BUNDLES:
        path = Path("vectors/valid") / name
        if not (ROOT / path).exists():
            record(f"sandwich {name}", INDET, "not present in this checkout")
            continue
        if not pq_ok:
            record(f"sandwich {name}", INDET,
                   "skipped: the toolchain cannot check PQ signatures")
            continue
        code, out = run([sys.executable, "scripts/verify_sandwich.py", str(path)])
        verdict = ""
        for line in out.splitlines():
            if '"verdict"' in line:
                verdict = line.strip().rstrip(",")
        record(f"sandwich {name}", PASS if code == 0 else FAIL,
               verdict or (out.strip().splitlines()[-1] if out.strip() else ""))

    if a.skip_network:
        record("Bitcoin attestations against a public explorer", INDET,
               "--skip-network was given; the proofs were not compared to any chain")
    else:
        code, out = run([sys.executable, "scripts/confirm_attestations.py"],
                        timeout=900)
        summary = ""
        for line in out.splitlines():
            if line.startswith("confirmed "):
                summary = line.strip()
        if code == 0:
            record("Bitcoin attestations against a public explorer", PASS, summary)
        elif code == 2:
            record("Bitcoin attestations against a public explorer", INDET,
                   summary or "explorer unreachable; nothing was contradicted")
        else:
            record("Bitcoin attestations against a public explorer", FAIL,
                   summary or "a proof disagrees with the chain")

    n_fail = sum(1 for r in results if r["status"] == FAIL)
    n_indet = sum(1 for r in results if r["status"] == INDET)
    n_pass = sum(1 for r in results if r["status"] == PASS)

    print(f"\n  {n_pass} passed · {n_fail} failed · {n_indet} could not be checked\n")
    if n_fail:
        print("  SOMETHING FAILED. That is a finding about this evidence, and it")
        print("  is the outcome worth reporting -- please open an issue with the")
        print("  output above.\n")
        verdict = "FAIL"
    elif n_indet:
        print("  NOTHING FAILED, but not everything was checked. That is not the")
        print("  same as success. The lines marked INDET say what was not asked")
        print("  and why -- usually a toolchain or a network, not the evidence.\n")
        verdict = "INDETERMINATE"
    else:
        print("  Everything that could be checked, was, and it held.\n")
        verdict = "PASS"

    if a.json:
        Path(a.json).write_text(json.dumps(
            {"verdict": verdict,
             "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "passed": n_pass, "failed": n_fail, "indeterminate": n_indet,
             "checks": results}, indent=2) + chr(10),
            encoding="utf-8", newline=chr(10))
        print(f"  written to {a.json}\n")

    return 1 if n_fail else (2 if n_indet else 0)


if __name__ == "__main__":
    sys.exit(main())
