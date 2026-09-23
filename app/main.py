"""Main FastAPI application entrypoint."""

import uuid
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import settings
from app.logging_config import logger
from app.models.errors import OSINTError, OSINTException


def create_app() -> FastAPI:
    """Factory creating configured FastAPI instance."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Isolated OSINT Intelligence Component for S.I.R.I.S.",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):
        """Attach a correlation/investigation ID and handle unhandled server errors."""
        request_id = request.headers.get("X-Investigation-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        except Exception as exc:
            logger.critical(f"Unhandled unexpected internal error [{request_id}]: {exc}", exc_info=True)
            error_response = OSINTError(
                error={
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An internal server error occurred while processing your request.",
                    "details": None,
                }
            )
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=error_response.model_dump(),
            )

        response.headers["X-Investigation-ID"] = request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors with structured OSINT format."""
        errors = exc.errors()
        messages = []
        cleaned_details = []
        for err in errors:
            loc = " -> ".join(str(l) for l in err.get("loc", []))
            msg = err.get("msg", "Invalid value")
            messages.append(f"{loc}: {msg}")
            clean_err = {
                "loc": [str(x) for x in err.get("loc", [])],
                "msg": msg,
                "type": err.get("type"),
            }
            if "ctx" in err:
                clean_err["ctx"] = {k: str(v) for k, v in err["ctx"].items()}
            cleaned_details.append(clean_err)

        combined_message = "; ".join(messages)
        req_id = getattr(request.state, "request_id", "unknown")
        logger.warning(f"Request validation failed [{req_id}]: {combined_message}")

        error_code = "INVALID_TARGET" if any("name" in str(d.get("loc", [])) for d in cleaned_details) else "INVALID_REQUEST"
        error_response = OSINTError(
            error={
                "code": error_code,
                "message": combined_message,
                "details": cleaned_details,
            }
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=error_response.model_dump(),
        )

    @app.exception_handler(OSINTException)
    async def osint_exception_handler(request: Request, exc: OSINTException):
        """Handle domain-specific OSINT exceptions."""
        logger.error(f"OSINT error [{getattr(request.state, 'request_id', 'unknown')}] {exc.code}: {exc.message}")
        error_response = OSINTError(
            error={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump(),
        )

    @app.exception_handler(Exception)
    async def global_unexpected_exception_handler(request: Request, exc: Exception):
        """Handle unexpected application errors (Category C) without leaking stack traces."""
        req_id = getattr(request.state, "request_id", "unknown")
        logger.critical(f"Unhandled unexpected internal error [{req_id}]: {exc}", exc_info=True)
        error_response = OSINTError(
            error={
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred while processing your request.",
                "details": None,
            }
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.model_dump(),
        )

    # Register routes
    app.include_router(router)

    return app


app = create_app()
