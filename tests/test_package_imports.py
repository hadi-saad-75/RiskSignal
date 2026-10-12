"""Smoke tests: the package and all sub-packages import cleanly."""

import importlib

import pytest

SUBPACKAGES = ["data", "stochastic", "graph", "tools", "agent", "api", "ui"]


def test_root_package_has_version() -> None:
    import risksignal

    assert isinstance(risksignal.__version__, str)


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_imports(name: str) -> None:
    module = importlib.import_module(f"risksignal.{name}")
    assert module.__doc__
