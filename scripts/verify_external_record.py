#!/usr/bin/env python3
"""Verify one external record and archive its preimage, before it can be bound.

The step between "the other system says it signed a record carrying our tag" and
scripts/close_binding_session.py. It is a script now because the delegation log
recurs weekly, and because doing it by hand lost a preimage once: epoch 11's record
was verified in memory and only its digest kept, and when the issuer later stopped
serving it by id the epoch became impossible for a third party to open. It was
recovered by luck from another session's scratchpad. This makes the archive the
first thing that happens, not an afterthought.

    python scripts/verify_external_record.py --work live/naxytra-delegation-work \
        --id att_xxxxxxxxxxxx --url https://.../checkpoints/att_xxxxxxxxxxxx

What it checks, in order, and refuses on any failure:
  1. the response parses and carries an `attestation` object
  2. SHA-256 of that object's RFC 8785 form equals the digest the issuer states
     (and --expect, if given -- e.g. the value in the issuer's incoming line)
  3. bindings[0] is exactly {scheme ctp/1, system_id <session>, tag <session>}
  4. the tag appears inside the signed object

Then it archives the full response to <work>/preimages/<id>.json -- gitignored, and
copied into the vault by tools/build_mn_backup.py -- and appends the record to
<work>/records.json as VERIFIED. Only digests and identifiers go into records.json;
the record's content stays out of the public repository (ADR-0008 s.4).

A work dir holding a file named `record-ids-private` keeps identifiers out too: a
stream of a system's paid attestations, where publishing every id would hand anyone
a list of what its buyers had attested. records.json then carries the digest alone,
the preimage is archived as preimages/<digest>.json, and the id and URL go to
preimages/index.jsonl, which is gitignored with the preimages. A holder of the
record still proves inclusion from the digest; nobody else can enumerate.

Exit codes: 0 verified and archived · 1 refused (record does not check) · 2 could not fetch
"""
from __future__ import annotations
import argparse, hashlib, json, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def jcs(obj) -> bytes:
    """RFC 8785 for the JSON this protocol meets: sorted keys, no whitespace, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", required=True)
    ap.add_argument("--id", required=True, help="the issuer's record id")
    ap.add_argument("--url", required=True, help="by-id URL serving the full record")
    ap.add_argument("--expect", default=None, help="digest the issuer reported, if any")
    a = ap.parse_args()

    work = ROOT / a.work
    ch = json.loads((work / "challenge.json").read_text(encoding="utf-8"))
    system_id, tag = ch["system_id"], ch["binding_tag"]

    try:
        raw = urllib.request.urlopen(a.url, timeout=30).read()
    except Exception as e:
        print(f"  COULD NOT FETCH {a.url}: {type(e).__name__}: {e}")
        return 2

    def refuse(why: str) -> int:
        print(f"\n  REFUSED  {a.id}\n  {why}\n  Nothing archived, nothing appended.\n")
        return 1

    try:
        resp = json.loads(raw)
    except ValueError:
        return refuse("response is not JSON")
    att = resp.get("attestation") if isinstance(resp, dict) else None
    if not isinstance(att, dict):
        return refuse("response carries no `attestation` object")

    digest = hashlib.sha256(jcs(att)).hexdigest()
    stated = resp.get("attestation_sha256")
    if stated is not None and stated != digest:
        return refuse(f"issuer states {stated}, recomputed {digest}")
    if a.expect and a.expect != digest:
        return refuse(f"expected {a.expect}, recomputed {digest}")
    b = att.get("bindings") or []
    want = {"scheme": "ctp/1", "system_id": system_id, "tag": tag}
    if not b or b[0] != want:
        return refuse(f"bindings[0] is {json.dumps(b[0]) if b else 'absent'}, want {json.dumps(want)}")
    if tag not in json.dumps(att):
        return refuse("tag not present inside the signed object")

    private = (work / "record-ids-private").exists()
    pre = work / "preimages"
    pre.mkdir(exist_ok=True)
    name = f"{digest}.json" if private else f"{a.id}.json"
    (pre / name).write_bytes(raw)
    if hashlib.sha256(jcs(json.loads((pre / name).read_bytes())["attestation"])).hexdigest() != digest:
        return refuse("archived copy does not recompute; disk problem")
    idx = pre / "index.jsonl"
    if private and digest not in (idx.read_text(encoding="utf-8") if idx.exists() else ""):
        with open(idx, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"id": a.id, "record_sha256": digest, "fetch": a.url}) + "\n")

    rp = work / "records.json"
    recs = (json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else
            {"record_type": "external_records_verified", "system_id": system_id, "records": []})
    if any(r.get("record_sha256") == digest for r in recs["records"]):
        print(f"  already recorded: {a.id} {digest}")
        return 0
    seq = max((r["seq"] for r in recs["records"]), default=-1) + 1
    entry = {"seq": seq, "id": a.id, "record_sha256": digest, "fetch": a.url}
    if private:
        entry = {"seq": seq, "record_sha256": digest}
    entry.update({
        "verified_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "recompute_matches": True, "tag_present_in_signed_bytes": True,
        "preimage_archived": f"preimages/{name}", "verdict": "VERIFIED",
    })
    recs["records"].append(entry)
    rp.write_text(json.dumps(recs, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(f"\n  VERIFIED  {a.id}  seq {seq}\n  digest    {digest}")
    print(f"  archived  {a.work}/preimages/{name}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
