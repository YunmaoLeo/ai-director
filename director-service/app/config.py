from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_provider: str = "mock"
    llm_model: str = "mock"
    llm_api_key: str = ""
    output_dir: Path = Path("outputs")
    log_level: str = "INFO"
    scenes_dir: Path = Path("scenes")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
