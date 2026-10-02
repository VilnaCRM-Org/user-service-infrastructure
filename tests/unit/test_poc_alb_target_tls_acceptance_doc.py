"""The TEST ALB-to-task TLS risk acceptance (D-2) must keep its markers."""

from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[2] / "docs" / "poc-alb-target-tls-acceptance.md"
TEST_ONLY_MARKER = "TEST only"
REQUIRED_MARKERS = (
    TEST_ONLY_MARKER,
    "D-2",
    "2026-09-30",
    "A-14",
    "a PROD stack with an HTTP target group is refused by admission",
)


def missing_markers(text: str) -> list[str]:
    """Return the required markers that ``text`` does not contain."""
    return [marker for marker in REQUIRED_MARKERS if marker not in text]


def test_acceptance_doc_carries_every_marker() -> None:
    assert missing_markers(DOC.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("marker", REQUIRED_MARKERS)
def test_doc_without_a_marker_fails(marker: str) -> None:
    text = DOC.read_text(encoding="utf-8").replace(marker, "")
    assert missing_markers(text) == [marker]


def test_doc_without_test_only_marker_fails() -> None:
    text = DOC.read_text(encoding="utf-8").replace(TEST_ONLY_MARKER, "")
    assert TEST_ONLY_MARKER in missing_markers(text)
