from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field

from app.settings import settings


class GapDimension(BaseModel):
    key: str
    label: str
    weight: float
    question_hint: str = ""
    options: list[str] = Field(default_factory=list)
    affects: list[str] = Field(default_factory=list)


class RenewalConfigLoader:
    def __init__(self, config_dir: Path | None = None):
        self.config_dir = config_dir or settings.abs_config_dir

    def get_allowed_domains(self) -> list[str]:
        domains_file = self.config_dir / "domains.yaml"
        if not domains_file.exists():
            return []
        with open(domains_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return data.get("allowed_domains", [])

    def get_gap_dimensions(self, category: str = "accident") -> list[GapDimension]:
        gap_file = self.config_dir / "gaps" / f"{category}.yaml"
        if not gap_file.exists():
            return []
        with open(gap_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            raw_dimensions = data.get("dimensions", [])
            return [GapDimension(**d) for d in raw_dimensions]


config_loader = RenewalConfigLoader()
