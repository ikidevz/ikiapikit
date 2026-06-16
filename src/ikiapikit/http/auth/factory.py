
from .base import AuthStrategy
from .strategies import NoAuth, BearerAuth, ApiKeyAuth, BasicAuth
from .oauth2 import OAuth2ClientCredentials

from ...core.models import AuthConfig
from ...core.exceptions import AuthError


def build_auth_strategy(cfg: AuthConfig) -> AuthStrategy:
    """Factory: build the correct AuthStrategy from an AuthConfig."""
    if cfg.type == "none":
        return NoAuth()
    if cfg.type == "bearer":
        return BearerAuth(cfg.token.get_secret_value())
    if cfg.type == "apikey":
        return ApiKeyAuth(
            api_key=cfg.api_key.get_secret_value(),
            header=cfg.api_key_header,
            query_param=cfg.api_key_query_param,
        )
    if cfg.type == "basic":
        return BasicAuth(
            cfg.username,
            cfg.password.get_secret_value(),
        )
    if cfg.type == "oauth2":
        return OAuth2ClientCredentials(
            client_id=cfg.client_id,
            client_secret=cfg.client_secret.get_secret_value(),
            token_url=cfg.token_url,
            scopes=cfg.scopes,
        )
    raise AuthError(f"Unknown auth type: {cfg.type}")
