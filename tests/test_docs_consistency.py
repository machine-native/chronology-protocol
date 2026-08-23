"""Documentation claims that drift are caught here, not by readers.

Outside review has now found three separate stale-documentation defects: an
undeclared dependency, a test count in VERIFY.md, and a test count in
RELEASE_STATUS.json. Fixing each by hand invites a fourth. These tests make the
claims self-enforcing instead.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def collected_test_count() -> int:
    """How many tests pytest actually collects, asked of pytest itself."""
    r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"],
                       cwd=ROOT, capture_output=True, text=True)
    m = re.search(r"(\d+)\s+tests?\s+collected", r.stdout)
    if m:
        return int(m.group(1))
    # older/newer pytest prints a bare summary line instead
    m = re.search(r"^(\d+)\s+tests?", r.stdout.strip().splitlines()[-1])
    assert m, f"could not read collection count from:\n{r.stdout[-600:]}"
    return int(m.group(1))


def test_release_status_test_count_is_current():
    status = json.loads((ROOT / "RELEASE_STATUS.json").read_text(encoding="utf-8"))
    declared = status.get("tests", "")
    m = re.search(r"(\d+)", declared)
    assert m, f"RELEASE_STATUS.json 'tests' has no number: {declared!r}"
    assert int(m.group(1)) == collected_test_count(), (
        f"RELEASE_STATUS.json says {declared!r} but the suite collects "
        f"{collected_test_count()} — regenerate it before releasing")


def test_verify_md_test_count_is_current():
    text = (ROOT / "VERIFY.md").read_text(encoding="utf-8")
    # The document deliberately promises zero FAILURES out of N tests rather
    # than N passed: several tests skip when optional evidence files are absent,
    # and a reader who sees "79 passed, 5 skipped" against a promise of "84
    # passed" cannot tell whether that matters. The count is still pinned.
    m = re.search(r"zero failures\*\* out of (\d+) tests", text)
    assert m, "VERIFY.md no longer states an expected test count in the known form"
    assert int(m.group(1)) == collected_test_count(), (
        f"VERIFY.md promises {m.group(1)} passed but the suite collects "
        f"{collected_test_count()}")


def test_no_document_claims_zero_third_party_packages_without_qualification():
    """The verification path is stdlib-only; the TEST SUITE needs pytest.

    A reviewer hit `ModuleNotFoundError: pytest` four lines below a promise that no
    third-party packages were needed. Any unqualified restatement of that promise
    fails here.
    """
    bad = []
    for name in ("VERIFY.md", "CALL-FOR-VERIFICATION.md"):
        p = ROOT / name
        if not p.is_file():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            low = line.lower()
            if "no third-party python packages are needed" in low:
                # must be qualified on the same line — e.g. "...on the verification path"
                if not re.search(r"verification path|commands? 2|except|other than|apart from", low):
                    bad.append(f"{name}:{i}: {line.strip()}")
    assert not bad, "unqualified 'no third-party packages' claim:\n" + "\n".join(bad)


def test_pytest_is_declared_as_a_dependency():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r"test\s*=\s*\[[^\]]*pytest", text), (
        "pyproject.toml instructs pytest but does not declare it")
