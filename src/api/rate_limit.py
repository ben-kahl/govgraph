"""Rate limiting utilities using SlowAPI with a Redis backend.

Uses the JWT ``sub`` claim as the rate-limit key so limits are enforced
per authenticated user rather than per IP (which is unusable behind API
Gateway).  Falls back to the remote address when no valid token is present.

The Redis URL is read from the ``REDIS_URL`` environment variable.  For
local development without Redis, omit the variable or set it to
``memory://`` to use the in-process store (resets on cold-start, but
sufficient for local testing).
"""

import logging
import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# Fall back to in-memory storage when REDIS_URL is not configured so that
# local development and unit tests work without a Redis instance.
_REDIS_URL: str = os.environ.get("REDIS_URL", "memory://")


def get_user_identifier(request: Request) -> str:
    """Return the JWT ``sub`` claim for use as a rate-limit key.

    Decodes the bearer token *without* signature verification solely to
    extract the subject identifier.  Full JWT validation is still performed
    by the ``get_current_user`` dependency on each protected endpoint.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The ``sub`` claim string, or the client IP address if no valid
        bearer token is present.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            from jose import jwt as jose_jwt  # noqa: PLC0415

            claims = jose_jwt.get_unverified_claims(auth[7:])
            sub = claims.get("sub")
            if sub:
                return sub
        except Exception:
            logger.debug("rate_limit: could not extract sub from token")
    return get_remote_address(request)


def _build_limiter() -> Limiter:
    """Instantiate the SlowAPI limiter, falling back to memory:// on Redis errors.

    Returns:
        A configured :class:`Limiter` instance using Redis when available,
        otherwise an in-memory limiter so that a Redis outage never takes the
        API down (fail-open).
    """
    if _REDIS_URL == "memory://":
        return Limiter(key_func=get_user_identifier, storage_uri="memory://")
    try:
        instance = Limiter(key_func=get_user_identifier, storage_uri=_REDIS_URL)
        # Probe the connection so a bad URL is caught here, not per-request.
        instance._storage.check()
        logger.info("rate_limit: Redis backend initialised (%s)", _REDIS_URL.split("@")[-1])
        return instance
    except Exception as exc:
        logger.error(
            "rate_limit: Redis unavailable (%s) — falling back to memory://",
            exc,
        )
        return Limiter(key_func=get_user_identifier, storage_uri="memory://")


limiter = _build_limiter()
