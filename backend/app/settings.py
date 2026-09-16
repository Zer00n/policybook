from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_secret: str = ""
    family_password: str = ""

    # Paths (always use pathlib.Path)
    project_root: Path = Path(__file__).resolve().parent.parent.parent
    data_dir: Path = Path("./data")
    models_dir: Path = Path("./models")
    config_dir: Path = Path("./config")

    # LLM Settings
    ark_api_key: str = ""
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    model_primary: str = "doubao-seed-evolving"
    model_baseline: str = "doubao-seed-2-1-pro-260628"

    soffice_path: str = ""
    http_proxy: str = ""
    eval_mode: bool = False

    def resolve_path(self, p: Path | str) -> Path:
        p = Path(p)
        if p.is_absolute():
            return p
        return (self.project_root / p).resolve()

    @property
    def abs_data_dir(self) -> Path:
        return self.resolve_path(self.data_dir)

    @property
    def abs_models_dir(self) -> Path:
        return self.resolve_path(self.models_dir)

    @property
    def abs_config_dir(self) -> Path:
        return self.resolve_path(self.config_dir)


settings = Settings()
