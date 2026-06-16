import tomli_w
import keyring
import tomllib

from pathlib import Path
from typing import Any, Optional

from ..core.constants import DEFAULT_CONFIG_FILE, DEFAULT_TIMEOUT, KEYRING_SERVICE
from ..core.types import AuthType
from ..core.exceptions import ConfigError, ConnectorNotFoundError
from ..core.models import ApiConfig, AuthConfig

_HAS_TOMLI_W = True
_HAS_KEYRING = True


class ConfigManager:
    """
    Manages apikit configuration stored in ~/.config/apikit/config.toml.
    Secrets are optionally stored in the OS keyring.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or DEFAULT_CONFIG_FILE
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        if self.config_path.exists():
            with open(self.config_path, "rb") as f:
                self._data = tomllib.load(f)
        else:
            self._data = {}

    def _save(self) -> None:
        if not _HAS_TOMLI_W:
            raise ConfigError("Saving config requires: pip install tomli-w")
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "wb") as f:
            tomli_w.dump(self._data, f)

    def list_connectors(self) -> list[str]:
        """Return names of all configured connectors."""
        return list(self._data.get("connectors", {}).keys())

    def get_connector_raw(self, name: str) -> Optional[dict]:
        """Return raw TOML dict for a connector."""
        return self._data.get("connectors", {}).get(name)

    def get_api_config(self, name: str) -> ApiConfig:
        """Build an ApiConfig from a named connector in the config file."""
        raw = self.get_connector_raw(name)
        if raw is None:
            raise ConnectorNotFoundError(
                f"Connector '{name}' not found in {self.config_path}. "
                f"Available: {self.list_connectors()}"
            )

        auth_type: AuthType = raw.get("auth_type", "none")
        token = raw.get("token")
        api_key = raw.get("api_key")

        if _HAS_KEYRING:
            if auth_type == "bearer" and not token:
                try:
                    token = keyring.get_password(
                        KEYRING_SERVICE, f"{name}.token")
                except Exception:
                    pass
            if auth_type == "apikey" and not api_key:
                try:
                    api_key = keyring.get_password(
                        KEYRING_SERVICE, f"{name}.api_key")
                except Exception:
                    pass

        auth_kwargs: dict[str, Any] = {"type": auth_type}
        if token:
            auth_kwargs["token"] = token
        if api_key:
            auth_kwargs["api_key"] = api_key
        if raw.get("username"):
            auth_kwargs["username"] = raw["username"]
            auth_kwargs["password"] = raw.get("password", "")
        if raw.get("client_id"):
            auth_kwargs.update({
                "client_id": raw["client_id"],
                "client_secret": raw.get("client_secret", ""),
                "token_url": raw.get("token_url", ""),
                "scopes": raw.get("scopes", []),
            })

        return ApiConfig(
            name=name,
            base_url=raw["base_url"],
            auth=AuthConfig(**auth_kwargs),
            headers=raw.get("headers", {}),
            timeout=raw.get("timeout", DEFAULT_TIMEOUT),
        )

    def add_connector(
        self,
        name: str,
        base_url: str,
        auth_type: AuthType = "none",
        token: Optional[str] = None,
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        store_secret_in_keyring: bool = True,
        **extra: Any,
    ) -> None:
        """Add or update a connector in the config file."""
        entry: dict[str, Any] = {"base_url": base_url, "auth_type": auth_type}
        entry.update(extra)

        if store_secret_in_keyring and _HAS_KEYRING:
            if token:
                keyring.set_password(KEYRING_SERVICE, f"{name}.token", token)
            if api_key:
                keyring.set_password(
                    KEYRING_SERVICE, f"{name}.api_key", api_key)
            if password:
                keyring.set_password(
                    KEYRING_SERVICE, f"{name}.password", password)
        else:
            if token:
                entry["token"] = token
            if api_key:
                entry["api_key"] = api_key
            if username:
                entry["username"] = username
            if password:
                entry["password"] = password

        if username:
            entry["username"] = username

        self._data.setdefault("connectors", {})[name] = entry
        self._save()

    def remove_connector(self, name: str) -> None:
        """Remove a connector from config."""
        connectors = self._data.get("connectors", {})
        if name not in connectors:
            raise ConnectorNotFoundError(f"Connector '{name}' not found.")
        del connectors[name]
        self._save()
        if _HAS_KEYRING:
            for suffix in ("token", "api_key", "password"):
                try:
                    keyring.delete_password(
                        KEYRING_SERVICE, f"{name}.{suffix}")
                except Exception:
                    pass
