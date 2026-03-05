from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    bot_token: str
    database_url: str = "postgresql+asyncpg://ritm:ritm@localhost:5432/ritm"
    redis_url: str = "redis://localhost:6379/0"
    model_path: str = "models/qwen2.5-3b-instruct-q4_k_m.gguf"
    model_n_ctx: int = 2048
    model_n_threads: int = 4
    model_n_gpu_layers: int = 0
    kb_dir: str = "./kb_data"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
