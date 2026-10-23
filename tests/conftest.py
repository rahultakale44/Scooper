"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture
def sample_config_dict():
    """Provide a sample configuration dictionary for testing."""
    return {
        "log_level": "INFO",
        "max_iterations": 10,
    }
