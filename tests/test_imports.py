"""Test that importing the integration triggers no Home Assistant deprecation report."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).parents[1]

IMPORT_EVERY_MODULE = """
import importlib, pkgutil
import custom_components.airfi_home as package
for module in pkgutil.walk_packages(package.__path__, f"{package.__name__}."):
    importlib.import_module(module.name)
"""


def test_importing_every_module_reports_no_deprecation() -> None:
    """A deprecated constant imported at module level is reported once, at import, before any test runs."""
    result = subprocess.run(
        [sys.executable, "-c", IMPORT_EVERY_MODULE],
        capture_output=True,
        check=True,
        cwd=ROOT,
        text=True,
    )

    assert "The deprecated" not in result.stderr, result.stderr
    assert "Detected that custom integration" not in result.stderr, result.stderr
