"""Unit tests for MCPSettings in generated xbridge_mcp.config"""

from xbridge_mcp.config import MCPSettings


class TestMCPSettingsDefaults:
    """Test default values for MCPSettings"""

    def test_default_transport(self):
        settings = MCPSettings()
        assert settings.transport == "stdio"

    def test_default_host(self):
        settings = MCPSettings()
        assert settings.host == "127.0.0.1"

    def test_default_port(self):
        settings = MCPSettings()
        assert settings.port == 8080

    def test_default_log_level(self):
        settings = MCPSettings()
        assert settings.log_level == "INFO"

    def test_default_allow_write(self):
        settings = MCPSettings()
        assert settings.allow_write is False


class TestMCPSettingsEnvOverrides:
    """Test environment variable overrides for MCPSettings"""

    def test_transport_http(self, monkeypatch):
        monkeypatch.setenv("MCP_TRANSPORT", "http")
        settings = MCPSettings()
        assert settings.transport == "http"

    def test_port_override(self, monkeypatch):
        monkeypatch.setenv("MCP_PORT", "9090")
        settings = MCPSettings()
        assert settings.port == 9090

    def test_host_override(self, monkeypatch):
        monkeypatch.setenv("MCP_HOST", "0.0.0.0")
        settings = MCPSettings()
        assert settings.host == "0.0.0.0"

    def test_log_level_override(self, monkeypatch):
        monkeypatch.setenv("MCP_LOG_LEVEL", "DEBUG")
        settings = MCPSettings()
        assert settings.log_level == "DEBUG"

    def test_allow_write_true(self, monkeypatch):
        monkeypatch.setenv("MCP_ALLOW_WRITE", "true")
        settings = MCPSettings()
        assert settings.allow_write is True

    def test_allow_write_false_unchanged(self, monkeypatch):
        monkeypatch.delenv("MCP_ALLOW_WRITE", raising=False)
        settings = MCPSettings()
        assert settings.allow_write is False
