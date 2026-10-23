"""Test configuration models."""

import pytest
from pydantic import ValidationError

from scooper.config import ModelProviderConfig, ScooperConfig
from scooper.exceptions import ConfigurationError


class TestScooperConfig:
    """Test ScooperConfig validation and behavior."""

    def test_default_config(self):
        """Test creating config with default values."""
        config = ScooperConfig()
        assert config.log_level == "INFO"
        assert config.max_iterations == 10
        assert config.timeout_seconds == 300

    def test_custom_config(self):
        """Test creating config with custom values."""
        config = ScooperConfig(
            log_level="DEBUG",
            max_iterations=20,
            timeout_seconds=600,
        )
        assert config.log_level == "DEBUG"
        assert config.max_iterations == 20
        assert config.timeout_seconds == 600

    def test_valid_log_levels(self):
        """Test all valid log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = ScooperConfig(log_level=level)
            assert config.log_level == level

    def test_invalid_log_level(self):
        """Test that invalid log level raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ScooperConfig(log_level="INVALID")
        # Pydantic raises ValidationError with literal_error type
        assert "literal_error" in str(exc_info.value) or "Invalid log level" in str(exc_info.value)

    def test_max_iterations_bounds(self):
        """Test max_iterations boundary validation."""
        # Valid boundary values
        ScooperConfig(max_iterations=1)
        ScooperConfig(max_iterations=100)

        # Below minimum
        with pytest.raises(ValidationError):
            ScooperConfig(max_iterations=0)

        # Above maximum
        with pytest.raises(ValidationError):
            ScooperConfig(max_iterations=101)

    def test_timeout_bounds(self):
        """Test timeout_seconds validation."""
        # Valid values
        ScooperConfig(timeout_seconds=0)  # No timeout
        ScooperConfig(timeout_seconds=1)
        ScooperConfig(timeout_seconds=3600)

        # Negative timeout not allowed
        with pytest.raises(ValidationError):
            ScooperConfig(timeout_seconds=-1)

    def test_config_immutable(self):
        """Test that config is immutable after creation."""
        config = ScooperConfig()
        with pytest.raises(ValidationError):
            config.log_level = "DEBUG"

    def test_extra_fields_forbidden(self):
        """Test that extra fields are rejected."""
        with pytest.raises(ValidationError):
            ScooperConfig(unknown_field="value")

    def test_config_dict_conversion(self):
        """Test converting config to dictionary."""
        config = ScooperConfig(log_level="DEBUG", max_iterations=5)
        config_dict = config.model_dump()
        assert config_dict["log_level"] == "DEBUG"
        assert config_dict["max_iterations"] == 5
        assert config_dict["timeout_seconds"] == 300


class TestModelProviderConfig:
    """Test ModelProviderConfig validation and behavior."""

    def test_valid_config(self):
        """Test creating a valid provider config."""
        config = ModelProviderConfig(
            provider_type="ollama",
            base_url="http://localhost:11434",
            model_name="llama2",
        )
        assert config.provider_type == "ollama"
        assert config.base_url == "http://localhost:11434"
        assert config.model_name == "llama2"
        assert config.api_key is None
        assert config.timeout_seconds == 30

    def test_config_with_api_key(self):
        """Test config with API key."""
        config = ModelProviderConfig(
            provider_type="openai",
            base_url="https://api.openai.com",
            model_name="gpt-4",
            api_key="sk-test-key",
        )
        assert config.api_key == "sk-test-key"

    def test_empty_provider_type(self):
        """Test that empty provider type is rejected."""
        with pytest.raises((ValidationError, ConfigurationError)) as exc_info:
            ModelProviderConfig(
                provider_type="",
                base_url="http://localhost:11434",
                model_name="llama2",
            )
        assert "provider_type cannot be empty" in str(exc_info.value)

    def test_whitespace_provider_type(self):
        """Test that whitespace-only provider type is rejected."""
        with pytest.raises((ValidationError, ConfigurationError)):
            ModelProviderConfig(
                provider_type="   ",
                base_url="http://localhost:11434",
                model_name="llama2",
            )

    def test_empty_base_url(self):
        """Test that empty base URL is rejected."""
        with pytest.raises((ValidationError, ConfigurationError)) as exc_info:
            ModelProviderConfig(
                provider_type="ollama",
                base_url="",
                model_name="llama2",
            )
        assert "base_url cannot be empty" in str(exc_info.value)

    def test_invalid_base_url_scheme(self):
        """Test that base URL must have http/https scheme."""
        with pytest.raises((ValidationError, ConfigurationError)) as exc_info:
            ModelProviderConfig(
                provider_type="ollama",
                base_url="localhost:11434",
                model_name="llama2",
            )
        assert "must start with http:// or https://" in str(exc_info.value)

    def test_https_base_url(self):
        """Test that HTTPS URLs are accepted."""
        config = ModelProviderConfig(
            provider_type="openai",
            base_url="https://api.openai.com",
            model_name="gpt-4",
        )
        assert config.base_url == "https://api.openai.com"

    def test_empty_model_name(self):
        """Test that empty model name is rejected."""
        with pytest.raises((ValidationError, ConfigurationError)) as exc_info:
            ModelProviderConfig(
                provider_type="ollama",
                base_url="http://localhost:11434",
                model_name="",
            )
        assert "model_name cannot be empty" in str(exc_info.value)

    def test_timeout_validation(self):
        """Test timeout validation."""
        # Valid timeout
        config = ModelProviderConfig(
            provider_type="ollama",
            base_url="http://localhost:11434",
            model_name="llama2",
            timeout_seconds=60,
        )
        assert config.timeout_seconds == 60

        # Zero timeout not allowed
        with pytest.raises(ValidationError):
            ModelProviderConfig(
                provider_type="ollama",
                base_url="http://localhost:11434",
                model_name="llama2",
                timeout_seconds=0,
            )

    def test_config_immutable(self):
        """Test that provider config is immutable."""
        config = ModelProviderConfig(
            provider_type="ollama",
            base_url="http://localhost:11434",
            model_name="llama2",
        )
        with pytest.raises(ValidationError):
            config.model_name = "new-model"

    def test_whitespace_trimming(self):
        """Test that whitespace is trimmed from string fields."""
        config = ModelProviderConfig(
            provider_type="  ollama  ",
            base_url="http://localhost:11434",
            model_name="  llama2  ",
        )
        assert config.provider_type == "ollama"
        assert config.model_name == "llama2"
