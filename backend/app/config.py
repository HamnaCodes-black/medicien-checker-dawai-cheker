from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    app_name: str = "DawaiCheck API"
    api_prefix: str = "/api"
    data_dir: Path = BACKEND_DIR / "data"
    reference_dir: Path | None = None
    registry_csv: Path | None = None
    demo_manifest: Path = PROJECT_DIR / "demo_data" / "manifest.json"
    registry_provider: str = "local_demo"
    ocr_engine: str = "auto"
    ocr_languages: str = "eng+urd"
    ocr_min_confidence: float = 0.35
    max_upload_mb: int = 15
    max_side_px: int = 2400
    comparison_width_px: int = 640
    analysis_retention_seconds: int = 0
    vision_llm_enabled: bool = False
    vision_llm_api_key: str | None = None
    vision_llm_base_url: str = "https://api.openai.com/v1"
    vision_llm_model: str = "gpt-4o-mini"
    vision_llm_timeout_seconds: float = 30.0
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    seed_demo_on_startup: bool = True
    scoring_config_path: Path | None = None

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def refs_dir(self) -> Path:
        return self.reference_dir or (self.data_dir / "references")

    @property
    def demo_registry_csv(self) -> Path:
        return self.registry_csv or (self.data_dir / "registry_demo.csv")

    @property
    def scoring_file(self) -> Path:
        return self.scoring_config_path or (Path(__file__).resolve().parent / "config" / "scoring.json")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
