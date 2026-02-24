import os
import logging
from typing import Dict, Optional

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt

logger = logging.getLogger(__name__)

COGNITO_REGION = os.environ.get("COGNITO_REGION", "us-east-1")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")

_jwks_cache: Optional[Dict] = None

# auto_error=False so we can raise 401 (not 403) when the header is absent
security = HTTPBearer(auto_error=False)


def _get_jwks() -> Dict:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    if not COGNITO_USER_POOL_ID:
        raise HTTPException(status_code=503, detail="Auth not configured: COGNITO_USER_POOL_ID missing")

    url = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    try:
        response = httpx.get(url, timeout=5)
        response.raise_for_status()
        _jwks_cache = response.json()
        return _jwks_cache
    except Exception as e:
        logger.error("Failed to fetch Cognito JWKS: %s", e)
        raise HTTPException(status_code=503, detail="Unable to fetch auth keys")


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = credentials.credentials
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token header")

    kid = unverified_header.get("kid")
    jwks = _get_jwks()

    key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if key is None:
        raise HTTPException(status_code=401, detail="Token signing key not found")

    pool_url = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            options={"verify_at_hash": False},
        )
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Token validation failed: {e}")

    if claims.get("iss") != pool_url:
        raise HTTPException(status_code=401, detail="Token issuer mismatch")
    if claims.get("token_use") != "access":
        raise HTTPException(status_code=401, detail="Token must be an access token")

    return claims
