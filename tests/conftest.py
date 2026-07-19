"""Shared fixtures for the AI Camera Centre test suite."""
from __future__ import annotations

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load the integration from custom_components/ for every test."""
    yield
