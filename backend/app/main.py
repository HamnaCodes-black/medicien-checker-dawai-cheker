from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import analyze, meta, references
from .services.demo_registry import write_demo_registry
from .services.reference_store import ReferenceStore, seed_demo_references


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    store = ReferenceStore(settings.refs_dir)
    if settings.seed_demo_on_startup:
        seed_demo_references(settings)
    app.state.reference_store = store
    app.state.settings = settings
    if settings.registry_provider.strip().lower() == "local_demo":
        csv_path = settings.demo_registry_csv
        if not csv_path.exists() or csv_path.stat().st_size == 0:
            write_demo_registry(csv_path, store.list())
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="DawaiCheck API",
        version="0.1.0",
        description=(
            "Packaging-only screening prototype. Cannot test chemical content and "
            "never certifies a medicine as genuine or safe."
        ),
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    application.include_router(analyze.router, prefix=settings.api_prefix)
    application.include_router(references.router, prefix=settings.api_prefix)
    application.include_router(meta.router, prefix=settings.api_prefix)

    @application.get("/")
    def root() -> dict[str, str]:
        return {
            "name": "DawaiCheck API",
            "disclaimer": (
                "Packaging screening aid only, not a laboratory test. If in doubt, "
                "confirm with a licensed pharmacist or DRAP."
            ),
            "docs": "/docs",
        }

    return application


app = create_app()
