"""Cross-check the hardening plan bundle's manifest and FR-14 traceability."""

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "specs/workload-wa-hardening"
LAST_BASELINE_DECISION = 15
FR14_PLATFORM_TESTS = {
    "test_poc_workload_admission.py",
    "test_poc_contract.py",
    "test_poc_workload_capabilities.py",
    "test_poc_workload_phase_entrypoint.py",
    "test_poc_workload_image_config.py",
}


def _manifest():
    text = (BUNDLE / "run-summary.md").read_text()
    section = text[text.index("## Artifacts (sha256") : text.index("## Gates")]
    return section, dict(
        (name, digest)
        for digest, name in re.findall(r"^([0-9a-f]{64})  (\S+)$", section, re.M)
    )


def _decisions_after_baseline(text):
    return {
        f"D-{number}"
        for number in map(int, re.findall(r"\bD-(\d+)\b", text))
        if number > LAST_BASELINE_DECISION
    }


def test_manifest_hashes_match_the_bundle_files():
    _, manifest = _manifest()
    assert len(manifest) == 7
    for name, digest in manifest.items():
        assert hashlib.sha256((BUNDLE / name).read_bytes()).hexdigest() == digest, name


def test_brief_amendments_are_recorded_in_front_matter_and_manifest_preface():
    brief = (BUNDLE / "brief.md").read_text()
    front_matter, body = brief.split("\n---\n", 1)
    revision = next(
        line for line in front_matter.splitlines() if line.startswith("revision:")
    )
    preface, _ = _manifest()
    brief_sentence = next(
        sentence
        for sentence in re.split(r"(?<=\.) ", preface)
        if "`brief.md` changed" in sentence
    )
    amended = _decisions_after_baseline(body)
    assert amended
    assert amended <= _decisions_after_baseline(revision)
    assert amended <= _decisions_after_baseline(brief_sentence)


def test_fr14_release_platform_refusal_is_traced_to_tests_that_refuse_it():
    prd = (BUNDLE / "prd.md").read_text()
    traced = prd[prd.index("### 5.1") : prd.index("### 5.2")]
    row = next(line for line in traced.splitlines() if line.startswith("| FR-14 |"))
    cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", row)[1:-1]]
    assert "`release.platform` is not `linux/amd64` is refused" in cells[2]
    named = set(re.findall(r"`(test_\w+\.py)`", cells[4]))
    assert FR14_PLATFORM_TESTS <= named
    for name in named:
        assert (ROOT / "tests/unit" / name).is_file(), name
