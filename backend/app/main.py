import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import config, security
from app.errors import ApiError
from app.routers import auth, claims, meta, users
from app.seed import init_db

log = logging.getLogger("reimbursement")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    security.burn_password_check("warm-up")  # build the dummy hash now, not on the first login
    yield


app = FastAPI(title="Reimbursement Management API", version="1.0.0", lifespan=lifespan)

# Credentialed CORS only for the configured frontend origin(s), never "*". In dev the Vite
# proxy makes every call same-origin anyway; this matters if the frontend is hosted elsewhere.
app.add_middleware(
    CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", config.CSRF_HEADER],
    expose_headers=["Content-Disposition", "Retry-After"],
)


def _error(status: int, code: str, message: str, fields: dict | None = None,
           headers: dict | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, headers=headers,
                        content={"error": {"code": code, "message": message, "fields": fields or {}}})


@app.exception_handler(ApiError)
async def _api_error(_req: Request, exc: ApiError):
    headers = dict(exc.headers)
    if exc.status_code == 401:
        headers.setdefault("WWW-Authenticate", "Bearer")
    return _error(exc.status_code, exc.code, exc.message, exc.fields, headers)


@app.exception_handler(RequestValidationError)
async def _validation_error(_req: Request, exc: RequestValidationError):
    fields: dict[str, str] = {}
    for err in exc.errors():
        name = str(err["loc"][-1]) if err["loc"] else "body"
        fields.setdefault(name, err["msg"].removeprefix("Value error, "))
    return _error(422, "VALIDATION_ERROR", "Please fix the highlighted fields.", fields)


@app.exception_handler(StarletteHTTPException)
async def _http_error(_req: Request, exc: StarletteHTTPException):
    code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
    return _error(exc.status_code, code, str(exc.detail))


@app.exception_handler(Exception)
async def _unhandled(_req: Request, exc: Exception):
    log.exception("Unhandled error", exc_info=exc)
    return _error(500, "INTERNAL_ERROR", "Something went wrong on our side. Please try again.")


app.include_router(meta.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(claims.router)