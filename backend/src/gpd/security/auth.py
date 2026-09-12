import secrets
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from gpd.api.errors import ApiEnvelope, ApiError


def verify_bearer_token(auth_header: str | None, expected_token: str) -> bool:
    """Verify Authorization header against expected token using constant-time comparison."""
    if not auth_header or not expected_token:
        return False

    parts = auth_header.strip().split(None, 1)
    if len(parts) != 2:
        return False

    scheme, token = parts
    if scheme.lower() != "bearer":
        return False

    return secrets.compare_digest(token, expected_token)


def is_protected_path(path: str) -> bool:
    """Check if the given request path requires authentication when an access token is configured.

    Protects /api/v1 and /health/ready.
    Leaves /health/live open and minimal.
    """
    if path.startswith("/api/v1"):
        return True
    if path == "/health/ready" or path.startswith("/health/ready/"):
        return True
    return False


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Middleware enforcing constant-time Bearer token check for protected endpoints when access token is configured."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = getattr(request.app.state, "settings", None)
        access_token: str | None = None
        if settings and settings.access_token:
            access_token = settings.access_token.get_secret_value()

        # Only enforce when an access token is configured
        if access_token and is_protected_path(request.url.path):
            auth_header = request.headers.get("authorization")
            if not verify_bearer_token(auth_header, access_token):
                envelope = ApiEnvelope[None](
                    ok=False,
                    error=ApiError(
                        code="unauthorized",
                        message="Invalid or missing bearer token",
                        retryable=False,
                    ),
                )
                return JSONResponse(
                    status_code=401,
                    content=envelope.model_dump(mode="json"),
                )

        return await call_next(request)
