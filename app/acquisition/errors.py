"""Acquisition error codes, classifications, and mapping helpers."""

# Machine-readable acquisition error codes
INVALID_URL = "INVALID_URL"
BLOCKED_PRIVATE_ADDRESS = "BLOCKED_PRIVATE_ADDRESS"
FETCH_TIMEOUT = "FETCH_TIMEOUT"
DNS_ERROR = "DNS_ERROR"
CONNECTION_ERROR = "CONNECTION_ERROR"
TLS_ERROR = "TLS_ERROR"
HTTP_BAD_REQUEST = "HTTP_BAD_REQUEST"
HTTP_UNAUTHORIZED = "HTTP_UNAUTHORIZED"
HTTP_FORBIDDEN = "HTTP_FORBIDDEN"
HTTP_NOT_FOUND = "HTTP_NOT_FOUND"
HTTP_RATE_LIMITED = "HTTP_RATE_LIMITED"
HTTP_CLIENT_ERROR = "HTTP_CLIENT_ERROR"
HTTP_SERVER_ERROR = "HTTP_SERVER_ERROR"
UNSUPPORTED_CONTENT_TYPE = "UNSUPPORTED_CONTENT_TYPE"
CONTENT_TOO_LARGE = "CONTENT_TOO_LARGE"
TOO_MANY_REDIRECTS = "TOO_MANY_REDIRECTS"

# Retryability classification map
RETRYABLE_MAP: dict[str, bool] = {
    INVALID_URL: False,
    BLOCKED_PRIVATE_ADDRESS: False,
    FETCH_TIMEOUT: True,
    DNS_ERROR: False,
    CONNECTION_ERROR: True,
    TLS_ERROR: False,
    HTTP_BAD_REQUEST: False,
    HTTP_UNAUTHORIZED: False,
    HTTP_FORBIDDEN: False,
    HTTP_NOT_FOUND: False,
    HTTP_RATE_LIMITED: True,
    HTTP_CLIENT_ERROR: False,
    HTTP_SERVER_ERROR: True,
    UNSUPPORTED_CONTENT_TYPE: False,
    CONTENT_TOO_LARGE: False,
    TOO_MANY_REDIRECTS: False,
}


def map_http_status_to_error(status_code: int) -> tuple[str, str, bool]:
    """Map an HTTP status code to an error code, message, and retryable boolean.

    Args:
        status_code: The HTTP response status code.

    Returns:
        tuple[str, str, bool]: (error_code, error_message, retryable)
    """
    if status_code == 400:
        return HTTP_BAD_REQUEST, "The remote server returned HTTP 400 Bad Request.", False
    elif status_code == 401:
        return HTTP_UNAUTHORIZED, "The remote server returned HTTP 401 Unauthorized.", False
    elif status_code == 403:
        return HTTP_FORBIDDEN, "The remote server denied access to the requested resource.", False
    elif status_code == 404:
        return HTTP_NOT_FOUND, "The remote server returned HTTP 404.", False
    elif status_code == 408:
        return FETCH_TIMEOUT, "The remote server did not respond within the configured timeout.", True
    elif status_code == 429:
        return HTTP_RATE_LIMITED, "The remote server returned HTTP 429.", True
    elif 400 <= status_code < 500:
        return HTTP_CLIENT_ERROR, f"The remote server returned client error HTTP {status_code}.", False
    elif 500 <= status_code < 600:
        return HTTP_SERVER_ERROR, f"The remote server returned HTTP {status_code}.", True
    else:
        return HTTP_CLIENT_ERROR, f"Unexpected response status HTTP {status_code}.", False
