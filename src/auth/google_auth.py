from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from functools import lru_cache, partial

import requests
from cachecontrol import CacheControl

from google.auth.exceptions import GoogleAuthError, TransportError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from src.config import Config

TokenClaims = Mapping[str, Any]
TokenVerifier = Callable[[str, str], TokenClaims]


class AuthenticationError(Exception):
    """Raised when a Google ID token is invalid or missing."""


class AuthenticationServiceError(Exception):
    """Raised when token verification cannot complete due to a service failure."""


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str


@lru_cache(maxsize=1)
def _get_cached_google_request() -> google_requests.Request:
    session = CacheControl(requests.Session())
    return google_requests.Request(session=session)


def _verify_oauth2_token(token: str, audience: str) -> TokenClaims:
    request = partial(_get_cached_google_request(), timeout=5)

    return id_token.verify_oauth2_token(
        token,
        request,
        audience=audience,
    )


def verify_google_id_token(
    token: str | None,
    config: Config,
    *,
    verify_token: TokenVerifier | None = None,
) -> AuthenticatedUser:
    if not isinstance(token, str) or not token.strip():
        raise AuthenticationError("Missing or invalid identity token")

    verifier = verify_token or _verify_oauth2_token
    try:
        claims = verifier(token.strip(), config.google_client_id)
    except TransportError as exc:
        raise AuthenticationServiceError(
            "Google token verification temporarily unavailable"
        ) from exc
    except (ValueError, GoogleAuthError, TypeError) as exc:
        raise AuthenticationError("Invalid identity token") from exc

    if not isinstance(claims, Mapping):
        raise AuthenticationError("Invalid identity token")

    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise AuthenticationError("Identity token is missing subject")

    return AuthenticatedUser(user_id=user_id.strip())
