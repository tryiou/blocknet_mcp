"""Unit tests for MCP server runner logic in main.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import xbridge_mcp.main as main_mod
from xbridge_mcp.main import create_mcp_server, get_client, run_server


class TestCreateMCPServer:
    """Tests for create_mcp_server function"""

    def test_fastmcp_constructed_with_correct_args(self, monkeypatch):
        # Mock settings and dependencies
        mock_mcp_settings = MagicMock()
        mock_mcp_settings.server_name = "Test MCP"
        mock_mcp_settings.host = "0.0.0.0"
        mock_mcp_settings.port = 1234
        mock_mcp_settings.log_level = "WARNING"

        mock_rpc_settings = MagicMock()

        monkeypatch.setattr("xbridge_mcp.main.get_settings", lambda: (mock_rpc_settings, mock_mcp_settings))
        monkeypatch.setattr("xbridge_mcp.main.setup_logging", lambda _: None)
        monkeypatch.setattr("xbridge_mcp.main.get_logger", lambda _: MagicMock())
        monkeypatch.setattr("xbridge_mcp.main.init_security", lambda _: None)
        monkeypatch.setattr("xbridge_mcp.main.register_generated_tools", lambda *_: None)
        # get_client is passed to register_generated_tools, but it's not used in the test, we can leave as MagicMock
        monkeypatch.setattr("xbridge_mcp.main.get_client", lambda: MagicMock())
        monkeypatch.setattr("xbridge_mcp.main.init_client", AsyncMock())
        monkeypatch.setattr("xbridge_mcp.main.init_client", AsyncMock())  # Mock async init

        with patch("xbridge_mcp.main.FastMCP") as mock_fastmcp:
            mcp = create_mcp_server()
            mock_fastmcp.assert_called_once_with(
                name="Test MCP",
                host="0.0.0.0",
                port=1234,
                log_level="WARNING",
            )
            assert mcp == mock_fastmcp.return_value

    def test_registers_tools_and_security(self, monkeypatch):
        mock_mcp_settings = MagicMock()
        mock_mcp_settings.server_name = "Test"
        mock_mcp_settings.host = "0.0.0.0"
        mock_mcp_settings.port = 8080
        mock_mcp_settings.log_level = "INFO"
        mock_rpc_settings = MagicMock()

        monkeypatch.setattr("xbridge_mcp.main.get_settings", lambda: (mock_rpc_settings, mock_mcp_settings))
        monkeypatch.setattr("xbridge_mcp.main.setup_logging", lambda _: None)
        monkeypatch.setattr("xbridge_mcp.main.get_logger", lambda _: MagicMock())
        mock_security = MagicMock()
        monkeypatch.setattr("xbridge_mcp.main.init_security", mock_security)
        mock_register = MagicMock()
        monkeypatch.setattr("xbridge_mcp.main.register_generated_tools", mock_register)
        monkeypatch.setattr("xbridge_mcp.main.init_client", AsyncMock())
        # Use a sentinel to ensure the exact get_client reference passed
        sentinel = object()
        monkeypatch.setattr("xbridge_mcp.main.get_client", sentinel)

        with patch("xbridge_mcp.main.FastMCP"):
            mcp = create_mcp_server()
            mock_security.assert_called_once_with(mock_mcp_settings)
            mock_register.assert_called_once_with(mcp, sentinel)


class TestRunServer:
    """Tests for run_server async function"""

    @pytest.mark.asyncio
    async def test_stdio_transport_calls_run_stdio_async(self, monkeypatch):
        # Setup settings with transport="stdio"
        mock_mcp_settings = MagicMock()
        mock_mcp_settings.transport = "stdio"
        mock_mcp_settings.log_level = "INFO"
        mock_rpc_settings = MagicMock()

        monkeypatch.setattr("xbridge_mcp.main.get_settings", lambda: (mock_rpc_settings, mock_mcp_settings))
        monkeypatch.setattr("xbridge_mcp.main.setup_logging", lambda _: None)
        monkeypatch.setattr("xbridge_mcp.main.get_logger", lambda _: MagicMock())
        monkeypatch.setattr("xbridge_mcp.main.init_security", lambda _: None)
        monkeypatch.setattr("xbridge_mcp.main.register_generated_tools", lambda *_: None)
        monkeypatch.setattr("xbridge_mcp.main.get_client", lambda: MagicMock())
        monkeypatch.setattr("xbridge_mcp.main.init_client", AsyncMock())

        mock_mcp = MagicMock()
        mock_mcp.run_stdio_async = AsyncMock()
        mock_mcp.run_streamable_http_async = AsyncMock()

        with patch("xbridge_mcp.main.create_mcp_server", return_value=mock_mcp):
            with patch("xbridge_mcp.main.cleanup_client", new_callable=AsyncMock) as mock_cleanup:
                await run_server()
                mock_mcp.run_stdio_async.assert_awaited_once()
                mock_mcp.run_streamable_http_async.assert_not_awaited()
                mock_cleanup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_http_transport_calls_run_streamable_http_async(self, monkeypatch):
        mock_mcp_settings = MagicMock()
        mock_mcp_settings.transport = "http"
        mock_mcp_settings.log_level = "INFO"
        mock_rpc_settings = MagicMock()

        monkeypatch.setattr("xbridge_mcp.main.get_settings", lambda: (mock_rpc_settings, mock_mcp_settings))
        monkeypatch.setattr("xbridge_mcp.main.setup_logging", lambda _: None)
        monkeypatch.setattr("xbridge_mcp.main.get_logger", lambda _: MagicMock())
        monkeypatch.setattr("xbridge_mcp.main.init_security", lambda _: None)
        monkeypatch.setattr("xbridge_mcp.main.register_generated_tools", lambda *_: None)
        monkeypatch.setattr("xbridge_mcp.main.get_client", lambda: MagicMock())
        monkeypatch.setattr("xbridge_mcp.main.init_client", AsyncMock())

        mock_mcp = MagicMock()
        mock_mcp.run_stdio_async = AsyncMock()
        mock_mcp.run_streamable_http_async = AsyncMock()

        with patch("xbridge_mcp.main.create_mcp_server", return_value=mock_mcp):
            with patch("xbridge_mcp.main.cleanup_client", new_callable=AsyncMock) as mock_cleanup:
                await run_server()
                mock_mcp.run_streamable_http_async.assert_awaited_once()
                mock_mcp.run_stdio_async.assert_not_awaited()
                mock_cleanup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_on_exception(self, monkeypatch):
        mock_mcp_settings = MagicMock()
        mock_mcp_settings.transport = "http"
        mock_mcp_settings.log_level = "INFO"
        mock_rpc_settings = MagicMock()

        monkeypatch.setattr("xbridge_mcp.main.get_settings", lambda: (mock_rpc_settings, mock_mcp_settings))
        monkeypatch.setattr("xbridge_mcp.main.setup_logging", lambda _: None)
        monkeypatch.setattr("xbridge_mcp.main.get_logger", lambda _: MagicMock())
        monkeypatch.setattr("xbridge_mcp.main.init_security", lambda _: None)
        monkeypatch.setattr("xbridge_mcp.main.register_generated_tools", lambda *_: None)
        monkeypatch.setattr("xbridge_mcp.main.get_client", lambda: MagicMock())
        monkeypatch.setattr("xbridge_mcp.main.init_client", AsyncMock())

        mock_mcp = MagicMock()
        mock_mcp.run_streamable_http_async = AsyncMock(side_effect=Exception("test error"))

        with patch("xbridge_mcp.main.create_mcp_server", return_value=mock_mcp):
            with patch("xbridge_mcp.main.cleanup_client", new_callable=AsyncMock) as mock_cleanup:
                with pytest.raises(Exception, match="test error"):
                    await run_server()
                # Even though run_streamable_http_async raised, cleanup should be called in finally
                mock_cleanup.assert_awaited_once()


def test_get_client_raises_when_uninitialized():
    """Test get_client raises RuntimeError if client is None"""
    # Ensure _xbridge_mcp_client is None
    main_mod._xbridge_mcp_client = None
    with pytest.raises(RuntimeError, match="RPC client not initialized"):
        get_client()
