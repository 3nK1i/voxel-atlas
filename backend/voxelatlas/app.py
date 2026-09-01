from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import AuthenticationService, InMemorySessionStore
from .config import AppSettings, ConfigurationError, load_settings
from .dicom_ingestion import (
    DicomDependencyUnavailable,
    DicomIngestionError,
    DicomIngestionService,
    DicomStudyValidationError,
    DicomUploadLimitExceeded,
)
from .dicom_volume import (
    CanonicalVolumeService,
    DicomPixelDecodeError,
    DicomVolumeDependencyUnavailable,
    DicomVolumeError,
    DicomVolumeValidationError,
)
from .passwords import verify_password


COOKIE_SAMESITE = "lax"
COOKIE_PATH = "/"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = REPOSITORY_ROOT / "web"


class LoginRequest(BaseModel):
    username: str = Field(max_length=254)
    password: str = Field(max_length=1024)


class AuthenticatedResponse(BaseModel):
    authenticated: bool
    username: str


class AnonymousResponse(BaseModel):
    authenticated: bool


def _build_auth_service(settings: AppSettings) -> AuthenticationService | None:
    if settings.auth_username is None or settings.auth_password_hash is None:
        return None
    return AuthenticationService(
        username=settings.auth_username,
        password_hash=settings.auth_password_hash,
        password_verifier=verify_password,
        session_store=InMemorySessionStore(),
        session_ttl=timedelta(minutes=settings.session_ttl_minutes),
    )


def create_app(
    *,
    settings: AppSettings | None = None,
    auth_service: AuthenticationService | None = None,
    dicom_service: DicomIngestionService | None = None,
    volume_service: CanonicalVolumeService | None = None,
) -> FastAPI:
    runtime_settings = load_settings() if settings is None else settings
    if (
        runtime_settings.environment == "production"
        and (
            runtime_settings.auth_username is None
            or runtime_settings.auth_password_hash is None
        )
    ):
        raise ConfigurationError(
            "production authentication credentials must be configured before the HTTP app starts"
        )
    service = auth_service if auth_service is not None else _build_auth_service(runtime_settings)
    study_service = (
        dicom_service
        if dicom_service is not None
        else DicomIngestionService(
            data_dir=runtime_settings.data_dir,
            max_upload_mib=runtime_settings.max_upload_mib,
        )
    )
    patient_volume_service = (
        volume_service
        if volume_service is not None
        else CanonicalVolumeService(data_dir=runtime_settings.data_dir)
    )

    app = FastAPI(title="VoxelAtlas", docs_url=None, redoc_url=None)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(runtime_settings.allowed_hosts),
    )
    app.state.settings = runtime_settings
    app.state.auth_service = service
    app.state.dicom_service = study_service
    app.state.volume_service = patient_volume_service

    app.mount("/assets", StaticFiles(directory=WEB_ROOT / "assets"), name="assets")
    app.mount("/css", StaticFiles(directory=WEB_ROOT / "css"), name="css")
    app.mount("/js", StaticFiles(directory=WEB_ROOT / "js"), name="js")

    def current_username(request: Request) -> str | None:
        current_service: AuthenticationService | None = request.app.state.auth_service
        if current_service is None:
            return None
        token = request.cookies.get(runtime_settings.session_cookie_name)
        return current_service.resolve_session(token)

    def require_username(request: Request) -> str:
        username = current_username(request)
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        return username

    @app.get("/", include_in_schema=False)
    def root(request: Request) -> RedirectResponse:
        destination = "/workspace" if current_username(request) is not None else "/login"
        return RedirectResponse(url=destination, status_code=status.HTTP_302_FOUND)

    @app.get("/login", include_in_schema=False)
    def login_page(request: Request):
        if current_username(request) is not None:
            return RedirectResponse(url="/workspace", status_code=status.HTTP_302_FOUND)
        return FileResponse(
            WEB_ROOT / "login.html",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/workspace", include_in_schema=False)
    def workspace(request: Request):
        if current_username(request) is None:
            return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        return FileResponse(
            WEB_ROOT / "index.html",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/auth/login", response_model=AuthenticatedResponse)
    def login(payload: LoginRequest, response: Response) -> dict[str, object]:
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication is not configured",
            )

        token = service.authenticate(payload.username, payload.password)
        if token is None:
            response.headers["Cache-Control"] = "no-store"
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"Cache-Control": "no-store"},
            )

        response.set_cookie(
            key=runtime_settings.session_cookie_name,
            value=token,
            max_age=runtime_settings.session_ttl_minutes * 60,
            httponly=True,
            secure=runtime_settings.secure_cookies,
            samesite=COOKIE_SAMESITE,
            path=COOKIE_PATH,
        )
        response.headers["Cache-Control"] = "no-store"
        return {"authenticated": True, "username": runtime_settings.auth_username or ""}

    @app.get("/api/auth/session")
    def session(request: Request, response: Response) -> dict[str, object]:
        response.headers["Cache-Control"] = "no-store"
        username = current_username(request)
        if username is None:
            return {"authenticated": False}
        return {"authenticated": True, "username": username}

    @app.post("/api/auth/logout", response_model=AnonymousResponse)
    def logout(request: Request, response: Response) -> dict[str, bool]:
        current_service: AuthenticationService | None = request.app.state.auth_service
        token = request.cookies.get(runtime_settings.session_cookie_name)
        if current_service is not None:
            current_service.logout(token)
        response.delete_cookie(
            key=runtime_settings.session_cookie_name,
            path=COOKIE_PATH,
            secure=runtime_settings.secure_cookies,
            httponly=True,
            samesite=COOKIE_SAMESITE,
        )
        response.headers["Cache-Control"] = "no-store"
        return {"authenticated": False}

    @app.get("/api/studies/latest")
    def latest_study(
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        current_service: DicomIngestionService = app.state.dicom_service
        return {"study": current_service.latest_public_study()}

    @app.post("/api/studies/dicom", status_code=status.HTTP_201_CREATED)
    def upload_dicom_study(
        files: list[UploadFile] = File(...),
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        current_service: DicomIngestionService = app.state.dicom_service
        try:
            descriptor = current_service.ingest(files)
        except DicomUploadLimitExceeded as exc:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=str(exc),
            ) from exc
        except DicomDependencyUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        except DicomStudyValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        except DicomIngestionError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        return {"study": descriptor.public_dict()}

    @app.post("/api/studies/latest/volume")
    def build_latest_volume(
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        current_service: CanonicalVolumeService = app.state.volume_service
        try:
            study = current_service.build_latest()
        except DicomVolumeDependencyUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        except (DicomVolumeValidationError, DicomPixelDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        except DicomVolumeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        return {"study": study}

    @app.get("/api/protected/ping")
    def protected_ping(username: str = Depends(require_username)) -> dict[str, object]:
        return {"ok": True, "username": username}

    return app
