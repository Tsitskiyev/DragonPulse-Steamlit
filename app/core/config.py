from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    app_name: str = "DragonPulse MVP"

    llm_provider: str = os.getenv("LLM_PROVIDER", "groq").lower()

    # Groq
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_base_url: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

    # DeepSeek (оставим как резерв)
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    db_url: str = os.getenv("DB_URL", "sqlite:///./dragonpulse.db")

settings = Settings()
