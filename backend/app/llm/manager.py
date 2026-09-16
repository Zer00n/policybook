import os
from pathlib import Path
from typing import Any
import yaml

from app.llm.ark import ArkProvider
from app.llm.base import LLMProvider
from app.settings import settings


class ModelManager:
    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or (settings.abs_config_dir / "models.yaml")
        self._config: dict[str, Any] = {}
        self.load_config()

    def load_config(self) -> None:
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = {"default": "evolving", "models": {}}

        # 优先使用 .env 中的配置覆盖模型 ID
        models = self._config.get("models", {})
        if "evolving" in models and settings.model_primary:
            models["evolving"]["model_id"] = settings.model_primary
        if "pro_0628" in models and settings.model_baseline:
            models["pro_0628"]["model_id"] = settings.model_baseline
            models["pro_0628"]["display_name"] = f"Baseline ({settings.model_baseline})"


    @property
    def default_model_key(self) -> str:
        return self._config.get("default", "evolving")

    def get_models_info(self) -> list[dict[str, Any]]:
        models_dict = self._config.get("models", {})
        result = []
        default_key = self.default_model_key
        for key, conf in models_dict.items():
            result.append({
                "key": key,
                "is_default": (key == default_key),
                "model_id": conf.get("model_id", ""),
                "display_name": conf.get("display_name", key),
                "provider": conf.get("provider", "ark"),
                "supports": conf.get("supports", []),
            })
        return result

    def get_provider(self, key: str | None = None) -> LLMProvider:
        key = key or self.default_model_key
        models_dict = self._config.get("models", {})
        conf = models_dict.get(key)
        if not conf:
            # Fallback to default
            conf = models_dict.get(self.default_model_key, {})
            if not conf:
                raise ValueError(f"Model configuration for '{key}' not found.")

        provider_name = conf.get("provider", "ark")
        base_url = conf.get("base_url", settings.ark_base_url)
        model_id = conf.get("model_id", settings.model_primary)
        api_key_env = conf.get("api_key_env", "ARK_API_KEY")
        api_key = os.environ.get(api_key_env, settings.ark_api_key)
        display_name = conf.get("display_name", key)

        if provider_name == "ark":
            return ArkProvider(
                model_id=model_id,
                base_url=base_url,
                api_key=api_key,
                display_name=display_name,
            )
        else:
            # Default to Ark or extend in M2
            return ArkProvider(
                model_id=model_id,
                base_url=base_url,
                api_key=api_key,
                display_name=display_name,
            )


model_manager = ModelManager()
