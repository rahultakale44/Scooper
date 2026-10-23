"""Test basic package functionality."""

import scooper


def test_package_imports():
    """Test that the package can be imported."""
    assert scooper is not None


def test_version_available():
    """Test that version information is available."""
    assert hasattr(scooper, "__version__")
    assert isinstance(scooper.__version__, str)
    assert len(scooper.__version__) > 0


def test_version_format():
    """Test that version follows semantic versioning."""
    version = scooper.__version__
    parts = version.split(".")
    assert len(parts) >= 2, "Version should have at least major.minor"
    assert parts[0].isdigit(), "Major version should be numeric"
    assert parts[1].isdigit(), "Minor version should be numeric"
