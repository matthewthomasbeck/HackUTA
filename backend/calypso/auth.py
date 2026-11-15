"""Bearer-token check for every non-dashboard endpoint."""
import hmac

from fastapi import HTTPException, Request, status


def require_token(request: Request) -> None:
    expected = request.app.state.settings.api_token
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if not expected or scheme.lower() != "bearer" or not hmac.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="bad or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
