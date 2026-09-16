import os
from pathlib import Path
import secrets
import base64
from app.settings import settings


def main():
    print("=== 初始化 PolicyBook 环境 ===")
    settings.abs_data_dir.mkdir(parents=True, exist_ok=True)
    settings.abs_models_dir.mkdir(parents=True, exist_ok=True)
    (settings.abs_data_dir / "llm_raw").mkdir(parents=True, exist_ok=True)
    (settings.abs_models_dir / "rapidocr").mkdir(parents=True, exist_ok=True)

    env_path = settings.project_root / ".env"
    if not env_path.exists():
        example_path = settings.project_root / ".env.example"
        secret = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
        if example_path.exists():
            content = example_path.read_text(encoding="utf-8")
            content = content.replace("APP_SECRET=", f"APP_SECRET={secret}")
            env_path.write_text(content, encoding="utf-8")
            print(f"已生成 .env 并写入随机密钥: {env_path}")
        else:
            env_path.write_text(f"APP_SECRET={secret}\n", encoding="utf-8")

    print("数据与模型目录创建完毕。")
    print("初始化完成。")


if __name__ == "__main__":
    main()
