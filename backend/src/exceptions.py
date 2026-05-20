from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import logging
import os

logger = logging.getLogger(__name__)
DEBUG_MODE = os.getenv("ENVIRONMENT", "loc") in ("loc", "dev")


def make_json_error(detail: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "code": status_code, "detail": detail},
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTPException: {exc.detail} (Status: {exc.status_code})")
    return make_json_error(exc.detail or "An unexpected error occurred.", exc.status_code)


async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    message = str(exc) if DEBUG_MODE else "An unexpected error occurred. Please try again later."
    return make_json_error(message, 500)
