"""
tests/test_config_registry.py  —  §10 & §11  ConfigManager + ConnectorRegistry.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kit import (
    Apikit,
    ApiConfig,
    AuthConfig,
    PaginationConfig,
    ConfigManager,
    ConnectorRegistry,
    ConnectorDefinition,
    ConnectorNotFoundError,
)


# ============================================================================
# §10  CONFIG MANAGER
# ============================================================================


class TestConfigManager:
    def test_list_connectors_empty_on_new_file(self, tmp_dir: Path):
        mgr = ConfigManager(config_path=tmp_dir / "config.toml")
        assert mgr.list_connectors() == []

    def test_add_and_list_connector(self, tmp_dir: Path):
        mgr = ConfigManager(config_path=tmp_dir / "config.toml")
        mgr.add_connector(
            "my_api",
            base_url="https://api.example.com",
            auth_type="bearer",
            token="tok",
            store_secret_in_keyring=False,
        )
        assert "my_api" in mgr.list_connectors()

    def test_get_connector_raw(self, tmp_dir: Path):
        mgr = ConfigManager(config_path=tmp_dir / "config.toml")
        mgr.add_connector("api", base_url="https://test.com", store_secret_in_keyring=False)
        raw = mgr.get_connector_raw("api")
        assert raw["base_url"] == "https://test.com"

    def test_get_api_config_builds_config(self, tmp_dir: Path):
        mgr = ConfigManager(config_path=tmp_dir / "config.toml")
        mgr.add_connector(
            "myapi",
            base_url="https://api.example.com",
            auth_type="bearer",
            token="tok",
            store_secret_in_keyring=False,
        )
        cfg = mgr.get_api_config("myapi")
        assert cfg.base_url == "https://api.example.com"

    def test_remove_connector(self, tmp_dir: Path):
        mgr = ConfigManager(config_path=tmp_dir / "config.toml")
        mgr.add_connector("api", base_url="https://test.com", store_secret_in_keyring=False)
        mgr.remove_connector("api")
        assert "api" not in mgr.list_connectors()

    def test_remove_nonexistent_raises(self, tmp_dir: Path):
        mgr = ConfigManager(config_path=tmp_dir / "config.toml")
        with pytest.raises(ConnectorNotFoundError):
            mgr.remove_connector("ghost")

    def test_get_nonexistent_raises(self, tmp_dir: Path):
        mgr = ConfigManager(config_path=tmp_dir / "config.toml")
        with pytest.raises(ConnectorNotFoundError):
            mgr.get_api_config("ghost")


# ============================================================================
# §11  CONNECTOR REGISTRY
# ============================================================================


class TestConnectorRegistry:
    def test_list_includes_built_ins(self):
        names = ConnectorRegistry.list()
        assert "github" in names
        assert "stripe" in names
        assert "hubspot" in names

    def test_get_known_connector(self):
        defn = ConnectorRegistry.get("github")
        assert defn.name == "github"
        assert "github.com" in defn.base_url

    def test_get_unknown_raises(self):
        with pytest.raises(ConnectorNotFoundError):
            ConnectorRegistry.get("nonexistent_connector_xyz")

    def test_register_new_connector(self):
        @ConnectorRegistry.register
        def _test_connector() -> ConnectorDefinition:
            return ConnectorDefinition(
                name="_test_reg_connector",
                base_url="https://test.example.com",
            )

        assert "_test_reg_connector" in ConnectorRegistry.list()
        defn = ConnectorRegistry.get("_test_reg_connector")
        assert defn.base_url == "https://test.example.com"

    def test_build_config_with_token(self):
        cfg = ConnectorRegistry.build_config("github", token="ghp_test")
        assert cfg.auth.type == "bearer"
        assert cfg.auth.token.get_secret_value() == "ghp_test"

    def test_build_config_without_token_uses_none_auth(self):
        cfg = ConnectorRegistry.build_config("github")
        assert cfg.auth.type == "none"

    def test_built_in_connectors_have_valid_base_urls(self):
        for name in ConnectorRegistry.list():
            defn = ConnectorRegistry.get(name)
            assert defn.base_url.startswith("https://"), \
                f"Connector '{name}' has non-HTTPS base_url: {defn.base_url}"
