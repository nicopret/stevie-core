from importlib.metadata import version

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from stevie.api.routes import router
from stevie.kernel import StevieKernel

API_PREFIX = "/api/v1"


def create_app(kernel: StevieKernel) -> FastAPI:
    app = FastAPI(title="Stevie API", version=version("stevie"))
    app.state.kernel = kernel
    app.include_router(router, prefix=API_PREFIX)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI's default validation detail echoes input, which may contain secrets.
        return JSONResponse(status_code=422, content={"detail": "Invalid request"})

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return app
