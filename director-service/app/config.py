from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_provider: str = "mock"
    llm_model: str = "mock"
    llm_api_key: str = ""
    output_dir: Path = Path("outputs")
    log_level: str = "INFO"
    scenes_dir: Path = Path("scenes")

    # Temporal planning settings
    temporal_sample_rate: float = 10.0
    temporal_max_duration: float = 120.0
    temporal_max_payload_size_kb: int = 2048
    temporal_beat_pass_model: str = ""
    temporal_shot_pass_model: str = ""
    temporal_critique_pass_model: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
