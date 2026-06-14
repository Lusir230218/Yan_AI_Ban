from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "研AI伴"
    DEBUG: bool = True

    DATABASE_URL: str = ""
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    NEO4J_HOST: str = "127.0.0.1"
    NEO4J_PORT: int = 7687
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""

    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai-proxy.org/v1"
    LLM_MODEL: str = "qwen3.5-flash"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
