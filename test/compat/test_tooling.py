"""Keep formatter versions aligned between requirements-dev and pre-commit."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _pinned_dev_versions() -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in (ROOT / "requirements-dev.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, version = line.split("==", 1)
        pins[name.strip().lower()] = version.strip()
    return pins


def _pre_commit_hook_revs() -> dict[str, str]:
    """Parse only black/isort revs without requiring PyYAML."""
    text = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    found: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        repo_match = re.match(r"\s*-\s*repo:\s*(.+)$", line)
        if repo_match:
            url = repo_match.group(1).strip()
            if url.endswith("/black"):
                current = "black"
            elif url.endswith("/isort"):
                current = "isort"
            else:
                current = None
            continue
        if current:
            rev_match = re.match(r"\s*rev:\s*(.+)$", line)
            if rev_match:
                found[current] = rev_match.group(1).strip().lstrip("v")
                current = None
    return found


def test_pre_commit_black_and_isort_match_requirements_dev():
    pins = _pinned_dev_versions()
    hooks = _pre_commit_hook_revs()
    assert "black" in pins and "isort" in pins
    assert hooks.get("black") == pins["black"], (
        f"pre-commit black={hooks.get('black')} != requirements-dev black={pins['black']}"
    )
    assert hooks.get("isort") == pins["isort"], (
        f"pre-commit isort={hooks.get('isort')} != requirements-dev isort={pins['isort']}"
    )
