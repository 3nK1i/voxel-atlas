from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import AuthenticationService, InMemorySessionStore
from .anatomy_reconstruction import (
    AnatomyReconstructionDependencyUnavailable,
    AnatomyReconstructionError,
    AnatomyReconstructionService,
    AnatomyReconstructionValidationError,
)
from .config import AppSettings, ConfigurationError, load_settings
from .dicom_ingestion import (
    DicomDependencyUnavailable,
    DicomIngestionError,
    DicomIngestionService,
    DicomStudyValidationError,
    DicomUploadLimitExceeded,
)
from .dicom_mpr import (
    CanonicalMprService,
    DicomMprDependencyUnavailable,
    DicomMprError,
    DicomMprValidationError,
)
from .dicom_volume import (
    CanonicalVolumeService,
    DicomPixelDecodeError,
    DicomVolumeDependencyUnavailable,
    DicomVolumeError,
    DicomVolumeValidationError,
)
from .passwords import verify_password
from .sample_catalog import (
    SampleStudyCatalogError,
    SampleStudyCatalogService,
    SampleStudyIntegrityError,
    SampleStudyNotFoundError,
)
from .segmentation import (
    SegmentationConflictError,
    SegmentationError,
    SegmentationJobService,
    SegmentationNotFoundError,
    SegmentationUnavailableError,
    SegmentationValidationError,
)
from .segmentation_label_maps import SegmentationLabelMapService
from .segmentation_corrections import SegmentationCorrectionService
from .segmentation_overlays import (
    OVERLAY_MEDIA_TYPE,
    SegmentationOverlayService,
)
from .segmentation_surfaces import (
    SURFACE_MEDIA_TYPE,
    SegmentationSurfaceService,
)
from .volume_rendering import (
    RENDERING_MEDIA_TYPE,
    VolumeRenderingDependencyUnavailable,
    VolumeRenderingError,
    VolumeRenderingService,
    VolumeRenderingValidationError,
)


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


class SegmentationJobCreateRequest(BaseModel):
    provider_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    )
    model_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    )
    device: str = Field(default="auto", min_length=1, max_length=16)
    parameters: dict[str, object] = Field(default_factory=dict)


class SegmentationCorrectionSessionCreateRequest(BaseModel):
    label_map_id: str = Field(pattern=r"^map-[0-9a-f]{32}$")


class SegmentationCorrectionActionCreateRequest(BaseModel):
    kind: str = Field(pattern=r"^(include|exclude|review)$")
    label_id: int = Field(ge=1, le=65535)
    center_lps_mm: list[float] = Field(min_length=3, max_length=3)
    radius_mm: float = Field(ge=0.5, le=25.0)
    plane: str = Field(pattern=r"^(axial|coronal|sagittal)$")


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
    mpr_service: CanonicalMprService | None = None,
    anatomy_service: AnatomyReconstructionService | None = None,
    volume_rendering_service: VolumeRenderingService | None = None,
    sample_catalog_service: SampleStudyCatalogService | None = None,
    segmentation_service: SegmentationJobService | None = None,
    segmentation_label_map_service: SegmentationLabelMapService | None = None,
    segmentation_overlay_service: SegmentationOverlayService | None = None,
    segmentation_surface_service: SegmentationSurfaceService | None = None,
    segmentation_correction_service: SegmentationCorrectionService | None = None,
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
    patient_mpr_service = (
        mpr_service
        if mpr_service is not None
        else CanonicalMprService(data_dir=runtime_settings.data_dir)
    )
    patient_anatomy_service = (
        anatomy_service
        if anatomy_service is not None
        else AnatomyReconstructionService(data_dir=runtime_settings.data_dir)
    )
    patient_volume_rendering_service = (
        volume_rendering_service
        if volume_rendering_service is not None
        else VolumeRenderingService(data_dir=runtime_settings.data_dir)
    )
    patient_segmentation_service = (
        segmentation_service
        if segmentation_service is not None
        else SegmentationJobService(data_dir=runtime_settings.data_dir)
    )
    patient_segmentation_label_map_service = (
        segmentation_label_map_service
        if segmentation_label_map_service is not None
        else SegmentationLabelMapService(
            data_dir=runtime_settings.data_dir,
            job_service=patient_segmentation_service,
        )
    )
    patient_sample_catalog_service = (
        sample_catalog_service
        if sample_catalog_service is not None
        else SampleStudyCatalogService(
            data_dir=runtime_settings.data_dir,
            dicom_service=study_service,
            label_map_service=patient_segmentation_label_map_service,
        )
    )
    patient_segmentation_overlay_service = (
        segmentation_overlay_service
        if segmentation_overlay_service is not None
        else SegmentationOverlayService(
            data_dir=runtime_settings.data_dir,
            mpr_service=patient_mpr_service,
            label_map_service=patient_segmentation_label_map_service,
        )
    )
    patient_segmentation_surface_service = (
        segmentation_surface_service
        if segmentation_surface_service is not None
        else SegmentationSurfaceService(
            data_dir=runtime_settings.data_dir,
            label_map_service=patient_segmentation_label_map_service,
            worker_python=runtime_settings.surface_worker_python,
        )
    )
    patient_segmentation_correction_service = (
        segmentation_correction_service
        if segmentation_correction_service is not None
        else SegmentationCorrectionService(
            data_dir=runtime_settings.data_dir,
            label_map_service=patient_segmentation_label_map_service,
        )
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
    app.state.mpr_service = patient_mpr_service
    app.state.anatomy_service = patient_anatomy_service
    app.state.volume_rendering_service = patient_volume_rendering_service
    app.state.sample_catalog_service = patient_sample_catalog_service
    app.state.segmentation_service = patient_segmentation_service
    app.state.segmentation_label_map_service = patient_segmentation_label_map_service
    app.state.segmentation_overlay_service = patient_segmentation_overlay_service
    app.state.segmentation_surface_service = patient_segmentation_surface_service
    app.state.segmentation_correction_service = patient_segmentation_correction_service

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

    @app.get("/api/sample-studies")
    def sample_studies(
        response: Response,
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        current_service: SampleStudyCatalogService = app.state.sample_catalog_service
        return {"samples": current_service.list_public()}

    @app.get("/api/sample-studies/{sample_id}/preview")
    def sample_study_preview(
        sample_id: str,
        username: str = Depends(require_username),
    ) -> FileResponse:
        del username
        current_service: SampleStudyCatalogService = app.state.sample_catalog_service
        try:
            preview_path = current_service.preview_path(sample_id)
        except SampleStudyNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        return FileResponse(
            preview_path,
            media_type="image/png",
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.post(
        "/api/sample-studies/{sample_id}/load",
        status_code=status.HTTP_201_CREATED,
    )
    def load_sample_study(
        sample_id: str,
        response: Response,
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        current_service: SampleStudyCatalogService = app.state.sample_catalog_service
        try:
            return current_service.load_sample(sample_id)
        except SampleStudyNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
                headers={"Cache-Control": "no-store"},
            ) from exc
        except SampleStudyIntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
                headers={"Cache-Control": "no-store"},
            ) from exc
        except DicomUploadLimitExceeded as exc:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=str(exc),
                headers={"Cache-Control": "no-store"},
            ) from exc
        except DicomDependencyUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
                headers={"Cache-Control": "no-store"},
            ) from exc
        except DicomStudyValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
                headers={"Cache-Control": "no-store"},
            ) from exc
        except (DicomIngestionError, SampleStudyCatalogError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
                headers={"Cache-Control": "no-store"},
            ) from exc

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

    @app.get("/api/studies/latest/mpr")
    def latest_mpr_descriptor(
        response: Response,
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        current_service: CanonicalMprService = app.state.mpr_service
        try:
            descriptor = current_service.descriptor_latest()
        except DicomMprDependencyUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        except DicomMprValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        except DicomMprError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        response.headers["Cache-Control"] = "no-store"
        return {"mpr": descriptor}

    @app.get("/api/studies/latest/mpr/{plane}")
    def latest_mpr_plane(
        plane: str,
        index: int = Query(ge=0),
        window: float = Query(gt=0.0, le=1_000_000.0),
        level: float = Query(ge=-1_000_000.0, le=1_000_000.0),
        username: str = Depends(require_username),
    ) -> Response:
        del username
        current_service: CanonicalMprService = app.state.mpr_service
        try:
            image = current_service.render_latest(
                plane,
                index=index,
                window=window,
                level=level,
            )
        except DicomMprDependencyUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        except DicomMprValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        except DicomMprError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        return Response(
            content=image.pixels,
            media_type="application/x-voxelatlas-gray8",
            headers={
                "Cache-Control": "no-store",
                "X-VoxelAtlas-Plane": image.plane,
                "X-VoxelAtlas-Index": str(image.index),
                "X-VoxelAtlas-Position-Mm": f"{image.position_mm:.6f}",
                "X-VoxelAtlas-Width": str(image.width),
                "X-VoxelAtlas-Height": str(image.height),
            },
        )

    @app.get("/api/studies/latest/reconstruction")
    def latest_reconstruction_status(
        response: Response,
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        current_service: AnatomyReconstructionService = app.state.anatomy_service
        try:
            reconstruction = current_service.inspect_latest()
        except AnatomyReconstructionDependencyUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        except AnatomyReconstructionValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        except AnatomyReconstructionError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        response.headers["Cache-Control"] = "no-store"
        return {"reconstruction": reconstruction}

    @app.get("/api/studies/latest/volume-rendering")
    def latest_volume_rendering_descriptor(
        response: Response,
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        current_service: VolumeRenderingService = app.state.volume_rendering_service
        try:
            descriptor = current_service.inspect_latest()
        except VolumeRenderingDependencyUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
                headers={"Cache-Control": "no-store"},
            ) from exc
        except VolumeRenderingValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
                headers={"Cache-Control": "no-store"},
            ) from exc
        except VolumeRenderingError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
                headers={"Cache-Control": "no-store"},
            ) from exc
        response.headers["Cache-Control"] = "no-store"
        return {"volume_rendering": descriptor}

    @app.post("/api/studies/latest/volume-rendering")
    def prepare_latest_volume_rendering(
        response: Response,
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        current_service: VolumeRenderingService = app.state.volume_rendering_service
        try:
            descriptor = current_service.prepare_latest()
        except VolumeRenderingDependencyUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
                headers={"Cache-Control": "no-store"},
            ) from exc
        except VolumeRenderingValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
                headers={"Cache-Control": "no-store"},
            ) from exc
        except VolumeRenderingError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
                headers={"Cache-Control": "no-store"},
            ) from exc
        response.headers["Cache-Control"] = "no-store"
        return {"volume_rendering": descriptor}

    @app.get("/api/studies/latest/volume-rendering/data")
    def latest_volume_rendering_data(
        revision: str = Query(
            min_length=64,
            max_length=64,
            pattern=r"^[0-9a-fA-F]{64}$",
        ),
        username: str = Depends(require_username),
    ) -> FileResponse:
        del username
        current_service: VolumeRenderingService = app.state.volume_rendering_service
        try:
            artifact_path, descriptor = current_service.artifact_latest(revision)
        except VolumeRenderingDependencyUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
                headers={"Cache-Control": "no-store"},
            ) from exc
        except VolumeRenderingValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
                headers={"Cache-Control": "no-store"},
            ) from exc
        except VolumeRenderingError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
                headers={"Cache-Control": "no-store"},
            ) from exc
        return FileResponse(
            artifact_path,
            media_type=RENDERING_MEDIA_TYPE,
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "X-VoxelAtlas-Volume-Revision": descriptor.revision,
                "X-VoxelAtlas-Volume-SHA256": descriptor.artifact_sha256,
            },
        )

    def raise_segmentation_http_error(exc: SegmentationError) -> None:
        if isinstance(exc, SegmentationNotFoundError):
            code = status.HTTP_404_NOT_FOUND
        elif isinstance(exc, (SegmentationConflictError, SegmentationUnavailableError)):
            code = status.HTTP_409_CONFLICT
        elif isinstance(exc, SegmentationValidationError):
            code = status.HTTP_422_UNPROCESSABLE_ENTITY
        else:
            code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=code,
            detail=str(exc),
            headers={"Cache-Control": "no-store"},
        ) from exc

    @app.get("/api/segmentation/models")
    def segmentation_models(
        response: Response,
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        current_service: SegmentationJobService = app.state.segmentation_service
        return {"models": current_service.list_models()}

    @app.get("/api/segmentation/devices")
    def segmentation_devices(
        response: Response,
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        current_service: SegmentationJobService = app.state.segmentation_service
        return {"devices": current_service.list_devices()}

    @app.post("/api/segmentation/jobs", status_code=status.HTTP_201_CREATED)
    def create_segmentation_job(
        payload: SegmentationJobCreateRequest,
        response: Response,
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        current_service: SegmentationJobService = app.state.segmentation_service
        try:
            job = current_service.create_job(
                provider_id=payload.provider_id,
                model_id=payload.model_id,
                device_request=payload.device,
                parameters=payload.parameters,
            )
        except SegmentationError as exc:
            raise_segmentation_http_error(exc)
        return {"job": job}

    @app.get("/api/segmentation/jobs")
    def segmentation_jobs(
        response: Response,
        limit: int = Query(default=50, ge=1, le=100),
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        current_service: SegmentationJobService = app.state.segmentation_service
        return {"jobs": current_service.list_jobs()[:limit]}

    @app.get("/api/segmentation/jobs/{job_id}")
    def segmentation_job(
        job_id: str,
        response: Response,
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        current_service: SegmentationJobService = app.state.segmentation_service
        try:
            job = current_service.get_job(job_id)
        except SegmentationError as exc:
            raise_segmentation_http_error(exc)
        return {"job": job}

    @app.post("/api/segmentation/jobs/{job_id}/cancel")
    def cancel_segmentation_job(
        job_id: str,
        response: Response,
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        current_service: SegmentationJobService = app.state.segmentation_service
        try:
            job = current_service.cancel_job(job_id)
        except SegmentationError as exc:
            raise_segmentation_http_error(exc)
        return {"job": job}

    @app.get("/api/segmentation/label-maps")
    def segmentation_label_maps(
        response: Response,
        study_id: str | None = Query(
            default=None,
            min_length=32,
            max_length=32,
            pattern=r"^[0-9a-f]{32}$",
        ),
        limit: int = Query(default=50, ge=1, le=100),
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        current_service: SegmentationLabelMapService = (
            app.state.segmentation_label_map_service
        )
        try:
            label_maps = current_service.list(study_id=study_id)
        except SegmentationError as exc:
            raise_segmentation_http_error(exc)
        return {"label_maps": label_maps[:limit]}

    @app.get("/api/segmentation/label-maps/{label_map_id}")
    def segmentation_label_map(
        label_map_id: str,
        response: Response,
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        current_service: SegmentationLabelMapService = (
            app.state.segmentation_label_map_service
        )
        try:
            label_map = current_service.get(label_map_id)
        except SegmentationError as exc:
            raise_segmentation_http_error(exc)
        return {"label_map": label_map}

    @app.get("/api/studies/latest/segmentation-overlay")
    def latest_segmentation_overlay_descriptor(
        response: Response,
        label_map_id: str | None = Query(
            default=None,
            min_length=36,
            max_length=36,
            pattern=r"^map-[0-9a-f]{32}$",
        ),
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        current_service: SegmentationOverlayService = (
            app.state.segmentation_overlay_service
        )
        try:
            overlay = current_service.descriptor_latest(label_map_id=label_map_id)
        except SegmentationError as exc:
            raise_segmentation_http_error(exc)
        return {"overlay": overlay}

    @app.get("/api/studies/latest/segmentation-overlay/{plane}")
    def latest_segmentation_overlay_plane(
        plane: str,
        index: int = Query(ge=0),
        label_map_id: str | None = Query(
            default=None,
            min_length=36,
            max_length=36,
            pattern=r"^map-[0-9a-f]{32}$",
        ),
        username: str = Depends(require_username),
    ) -> Response:
        del username
        current_service: SegmentationOverlayService = (
            app.state.segmentation_overlay_service
        )
        try:
            image = current_service.render_latest(
                plane,
                index=index,
                label_map_id=label_map_id,
            )
        except SegmentationError as exc:
            raise_segmentation_http_error(exc)
        return Response(
            content=image.pixels,
            media_type=OVERLAY_MEDIA_TYPE,
            headers={
                "Cache-Control": "no-store",
                "X-VoxelAtlas-Plane": image.plane,
                "X-VoxelAtlas-Index": str(image.index),
                "X-VoxelAtlas-Position-Mm": f"{image.position_mm:.6f}",
                "X-VoxelAtlas-Width": str(image.width),
                "X-VoxelAtlas-Height": str(image.height),
                "X-VoxelAtlas-Label-Map-Id": image.label_map_id,
            },
        )

    @app.get("/api/studies/latest/segmentation-surfaces")
    def latest_segmentation_surface_descriptor(
        response: Response,
        label_map_id: str | None = Query(
            default=None,
            min_length=36,
            max_length=36,
            pattern=r"^map-[0-9a-f]{32}$",
        ),
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        current_service: SegmentationSurfaceService = (
            app.state.segmentation_surface_service
        )
        try:
            surface = current_service.descriptor_latest(label_map_id=label_map_id)
        except SegmentationError as exc:
            raise_segmentation_http_error(exc)
        return {"surface": surface}

    @app.get("/api/studies/latest/segmentation-surfaces/{label_id}")
    def latest_segmentation_surface(
        label_id: int,
        label_map_id: str = Query(
            min_length=36,
            max_length=36,
            pattern=r"^map-[0-9a-f]{32}$",
        ),
        quality: str = Query(default="accurate", pattern=r"^(accurate|preview|balanced)$"),
        username: str = Depends(require_username),
    ) -> Response:
        del username
        current_service: SegmentationSurfaceService = (
            app.state.segmentation_surface_service
        )
        try:
            surface = current_service.surface_latest(
                label_id=label_id,
                label_map_id=label_map_id,
                quality=quality,
            )
        except SegmentationError as exc:
            raise_segmentation_http_error(exc)
        bounds = ",".join(f"{value:.6f}" for value in surface.bounds_lps_mm)
        return Response(
            content=surface.payload,
            media_type=surface.media_type,
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "X-VoxelAtlas-Label-Map-Id": surface.label_map_id,
                "X-VoxelAtlas-Label-Id": str(surface.label_id),
                "X-VoxelAtlas-Surface-Quality": surface.quality,
                "X-VoxelAtlas-Surface-Extraction": surface.extraction,
                "X-VoxelAtlas-Surface-SHA256": surface.payload_sha256,
                "X-VoxelAtlas-Surface-Vertices": str(surface.vertex_count),
                "X-VoxelAtlas-Surface-Triangles": str(surface.triangle_count),
                "X-VoxelAtlas-Surface-Stride": str(surface.stride),
                "X-VoxelAtlas-Surface-Schema": str(surface.schema_version),
                "X-VoxelAtlas-Surface-Id": surface.surface_id,
                "X-VoxelAtlas-Surface-Provenance-SHA256": surface.provenance_sha256,
                "X-VoxelAtlas-Surface-Bounds-LPS-Mm": bounds,
            },
        )

    @app.get("/api/studies/latest/segmentation-quality/{label_id}")
    def latest_segmentation_quality(
        label_id: int,
        response: Response,
        label_map_id: str = Query(
            min_length=36,
            max_length=36,
            pattern=r"^map-[0-9a-f]{32}$",
        ),
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        current_service: SegmentationCorrectionService = (
            app.state.segmentation_correction_service
        )
        try:
            report = current_service.quality_report(
                label_map_id=label_map_id,
                label_id=label_id,
            )
        except SegmentationError as exc:
            raise_segmentation_http_error(exc)
        return {"quality": report}

    @app.post("/api/segmentation/correction-sessions", status_code=status.HTTP_201_CREATED)
    def create_segmentation_correction_session(
        payload: SegmentationCorrectionSessionCreateRequest,
        response: Response,
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        current_service: SegmentationCorrectionService = (
            app.state.segmentation_correction_service
        )
        try:
            session = current_service.create(payload.label_map_id)
        except SegmentationError as exc:
            raise_segmentation_http_error(exc)
        return {"correction_session": session}

    @app.get("/api/segmentation/correction-sessions")
    def list_segmentation_correction_sessions(
        response: Response,
        label_map_id: str = Query(
            min_length=36,
            max_length=36,
            pattern=r"^map-[0-9a-f]{32}$",
        ),
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        try:
            sessions = app.state.segmentation_correction_service.list(
                label_map_id=label_map_id
            )
        except SegmentationError as exc:
            raise_segmentation_http_error(exc)
        return {"correction_sessions": sessions}

    @app.get("/api/segmentation/correction-sessions/{session_id}")
    def get_segmentation_correction_session(
        session_id: str,
        response: Response,
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        current_service: SegmentationCorrectionService = (
            app.state.segmentation_correction_service
        )
        try:
            session = current_service.get(session_id)
        except SegmentationError as exc:
            raise_segmentation_http_error(exc)
        return {"correction_session": session}

    @app.post("/api/segmentation/correction-sessions/{session_id}/actions")
    def add_segmentation_correction_action(
        session_id: str,
        payload: SegmentationCorrectionActionCreateRequest,
        response: Response,
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        current_service: SegmentationCorrectionService = (
            app.state.segmentation_correction_service
        )
        try:
            session = current_service.add_action(
                session_id,
                kind=payload.kind,
                label_id=payload.label_id,
                center_lps_mm=payload.center_lps_mm,
                radius_mm=payload.radius_mm,
                plane=payload.plane,
            )
        except SegmentationError as exc:
            raise_segmentation_http_error(exc)
        return {"correction_session": session}

    @app.post("/api/segmentation/correction-sessions/{session_id}/undo")
    def undo_segmentation_correction(
        session_id: str,
        response: Response,
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        try:
            session = app.state.segmentation_correction_service.undo(session_id)
        except SegmentationError as exc:
            raise_segmentation_http_error(exc)
        return {"correction_session": session}

    @app.post("/api/segmentation/correction-sessions/{session_id}/redo")
    def redo_segmentation_correction(
        session_id: str,
        response: Response,
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        try:
            session = app.state.segmentation_correction_service.redo(session_id)
        except SegmentationError as exc:
            raise_segmentation_http_error(exc)
        return {"correction_session": session}

    @app.post("/api/segmentation/correction-sessions/{session_id}/discard")
    def discard_segmentation_correction(
        session_id: str,
        response: Response,
        username: str = Depends(require_username),
    ) -> dict[str, object]:
        del username
        response.headers["Cache-Control"] = "no-store"
        try:
            session = app.state.segmentation_correction_service.discard(session_id)
        except SegmentationError as exc:
            raise_segmentation_http_error(exc)
        return {"correction_session": session}

    @app.get("/api/protected/ping")
    def protected_ping(username: str = Depends(require_username)) -> dict[str, object]:
        return {"ok": True, "username": username}

    return app
