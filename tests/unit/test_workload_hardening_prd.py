"""Recompute the hardening PRD automation denominator from its own tables."""

import re
from pathlib import Path

PRD = Path(__file__).resolve().parents[2] / "specs/workload-wa-hardening/prd.md"


def _cells(line):
    """Split one Markdown table row on unescaped pipes only."""
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line)[1:-1]]


def _section(text, start, end):
    return text[text.index(start) : text.index(end)]


def _rows(section, prefix):
    return {
        cells[0]: cells
        for cells in (
            _cells(line)
            for line in section.splitlines()
            if re.match(rf"^\| {prefix}-\d{{2}} \|", line)
        )
    }


def _summary(text):
    rows = [
        _cells(line)
        for line in _section(text, "## 1.", "## 2.").splitlines()
        if line.startswith("| ") and not line.startswith(("| ---", "| Category"))
    ]
    return {cells[0].split(" (")[0]: cells[1:] for cells in rows}


def _numbered(cell, prefix):
    """Expand ``NFR-01, -02`` lists and ``FR-01 … FR-28`` ranges into IDs."""
    ids = set()
    for first, last in re.findall(rf"{prefix}-(\d{{2}}) … {prefix}-(\d{{2}})", cell):
        ids.update(f"{prefix}-{n:02d}" for n in range(int(first), int(last) + 1))
    ids.update(f"{prefix}-{n}" for n in re.findall(rf"(?:{prefix})?-(\d{{2}})\b", cell))
    return ids


def test_prd_counts():
    text = PRD.read_text()
    requirements = _section(text, "## 3.", "## 4.")
    functional = _rows(requirements, "FR")
    non_functional = _rows(_section(text, "## 4.", "## 5."), "NFR")
    traced = _rows(_section(text, "### 5.1", "### 5.2"), "FR")
    denominator = re.search(
        r"\*\*Automation denominator:\*\* (\d+) FRs and (\d+) NFRs, (\d+) "
        r"requirements in total\.",
        text,
    )
    assert denominator is not None
    fr_count, nfr_count, total = map(int, denominator.groups())
    assert sorted(functional) == [f"FR-{n:02d}" for n in range(1, fr_count + 1)]
    assert sorted(non_functional) == [f"NFR-{n:02d}" for n in range(1, nfr_count + 1)]
    assert set(traced) == set(functional)
    assert total == len(functional) + len(non_functional)

    kinds = {key: row[-1] for key, row in non_functional.items()}
    assert set(kinds.values()) == {"offline", "offline + live", "evidence-only"}
    offline_nfr = {key for key, kind in kinds.items() if kind.startswith("offline")}
    evidence_only = {key for key, kind in kinds.items() if kind == "evidence-only"}
    offline_live = {key for key, kind in kinds.items() if kind == "offline + live"}
    live_fr = {key for key, row in functional.items() if "L" in row[-1].split(", ")}
    assert live_fr == {key for key, row in traced.items() if row[-1] != "—"}

    summary = _summary(text)
    offline_row = summary["Offline-testable requirements"]
    assert offline_row[0] == f"{len(functional) + len(offline_nfr)}/{total}"
    assert offline_row[1].startswith(f"All {len(functional)} FRs, plus ")
    assert _numbered(offline_row[1].split("plus ")[1], "NFR") == offline_nfr
    evidence_row = summary["Evidence-only NFRs"]
    assert evidence_row == [str(len(evidence_only)), evidence_row[1]]
    assert _numbered(evidence_row[1], "NFR") == evidence_only
    live_row = summary["FRs that also require live TEST evidence"]
    assert live_row[0] == str(len(live_fr))
    stated = _numbered(live_row[1].split(" (")[0], "FR")
    excepted = re.search(r"every FR except (FR-\d{2})", live_row[1])
    assert excepted is not None
    assert stated == live_fr == set(functional) - {excepted.group(1)}
    carried = summary["Offline-testable NFRs that also carry live evidence"]
    assert carried[0] == str(len(offline_live))
    assert set(re.findall(r"NFR-\d{2}", carried[1])) == offline_live
