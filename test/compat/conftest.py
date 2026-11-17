"""Shared fixtures and pytest hooks for dependency compatibility tests."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

import pytest

# Distribution name on PyPI -> import / lookup name used in reports.
_RUNTIME_PACKAGES = (
    "aiohttp",
    "aiohttp-cors",
    "aiohttp-swagger3",
    "aiosmtplib",
    "asyncpg",
    "attrs",
    "Babel",
    "fuzzywuzzy",
    "glom",
    "holidays",
    "httpx",
    "jinja2",
    "jinja2-ansible-filters",
    "jq",
    "lark",
    "Markdown",
    "mautrix",
    "nats-py",
    "openai",
    "phonenumbers",
    "pillow",
    "pycountry",
    "python-Levenshtein",
    "python-magic",
    "pytz",
    "ruamel.yaml",
    "yarl",
)


def _installed_version(dist_name: str) -> str:
    try:
        return importlib.metadata.version(dist_name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def pytest_report_header(config: pytest.Config) -> list[str]:
    """Print Python and third-party versions used by the compat suite."""
    lines = ["menuflow compat: dependency versions"]
    for name in _RUNTIME_PACKAGES:
        lines.append(f"  {name}=={_installed_version(name)}")
    return lines


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Mark every test under test/compat/ with the ``compat`` marker."""
    compat_root = Path(__file__).resolve().parent
    marker = pytest.mark.compat
    for item in items:
        try:
            Path(item.path).resolve().relative_to(compat_root)
        except ValueError:
            continue
        item.add_marker(marker)
