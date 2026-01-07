import os

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from agentic_fs_archaeologist.app_logger import get_logger
from agentic_fs_archaeologist.exceptions import ConfigurationError


logger = get_logger(__name__)
dotenv_file_name = "filesystem-archaeologist-agent.env"
dotenv_path = Path(__file__).parent.parent.parent / dotenv_file_name
load_dotenv(dotenv_path)


class Settings():
    """
    Application settings.
    """
    # OpenAI Configuration
    openai_api_key: str = os.getenv("OPENAI_API_KEY", default="not-set")
    model_name: str = os.getenv("MODEL_NAME", default="gpt-4o-mini")

    # Agent Configuration
    max_iterations: int = int(os.getenv("MAX_ITERATIONS", default="10"))
    temperature: float = float(os.getenv("TEMPERATURE", default="0.3"))

    # Cleanup Configuration
    min_size_bytes: int = int(os.getenv("MIN_SIZE_BYTES",
                              default="1073741824"))  # 1GB
    min_age_days: int = int(os.getenv("MIN_AGE_DAYS", default="90"))

    # Safety Configuration
    enable_reflection: bool = bool(os.getenv("ENABLE_REFLECTION",
                                             default="True"))

    # Memory Configuration
    enable_memory: bool = bool(os.getenv("ENABLE_MEMORY", default="True"))
    memory_db_path: Path = Path(os.getenv("MEMORY_DB_PATH",
                                          default="memory.db"))

    # Cache Configuration
    classifier_cache_ttl: int = int(os.getenv("CLASSIFIER_CACHE_TTL",
                                              default="3600"))

    # Paths
    data_dir: Path = Path(os.getenv("DATA_DIR", default="."))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create directories if they do not exist
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.memory_db_path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            # Log the error and raise a more descriptive exception
            error_message = f"Permission denied when creating directories: {e}"
            logger.error(error_message)
            raise ConfigurationError(error_message)
        except OSError as e:
            error_message = f"Error creating directories: {e}"
            logger.error(error_message)
            raise ConfigurationError(error_message)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get global settings instance.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings():
    """
    Reset settings (mainly for testing).
    """
    global _settings
    _settings = None
