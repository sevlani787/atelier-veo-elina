import os
from dataclasses import dataclass
from dotenv import load_dotenv

from pathlib import Path

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

@dataclass
class Config:
    base_dir: Path = BASE_DIR
    # Telegram
    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    admin_id: int = int(os.getenv("ADMIN_ID", "0"))
    telegram_api_server: str = os.getenv("TELEGRAM_API_SERVER", "")
    max_video_size_mb: int = int(os.getenv("MAX_VIDEO_SIZE_MB", "2000" if os.getenv("TELEGRAM_API_SERVER") else "20"))

    # OpenRouter
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = "google/gemini-2.5-flash"
    cheap_model: str = "google/gemini-2.5-flash"

    # Search APIs
    brave_api_key: str = os.getenv("BRAVE_API_KEY", "")
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    apify_api_token: str = os.getenv("APIFY_API_TOKEN", "")

    # Memory
    max_context_messages: int = 15

    async def get_model(self) -> str:
        """Получение текущей модели ИИ (из БД или дефолт)."""
        from bot.services.database import db
        return await db.get_setting("ai_model", self.openrouter_model)

    async def get_token_cost(self, action: str = "msg", with_search: bool = False) -> int:
        """Получение стоимости запроса в Atelier Credits."""
        from bot.services.database import db
        if with_search or action == "audit":
            val = await db.get_setting("credit_cost_audit", "50")
            return int(val)
        if action == "qa":
            val = await db.get_setting("credit_cost_qa", "25")
            return int(val)
        if action == "prompt":
            val = await db.get_setting("credit_cost_prompt", "20")
            return int(val)
        if action in ("remediation", "shield", "finishing"):
            val = await db.get_setting("credit_cost_remediation", "100")
            return int(val)
        if action == "ambassador":
            val = await db.get_setting("credit_cost_ambassador", "100")
            return int(val)
        val = await db.get_setting("credit_cost_msg", "1")
        return int(val)

    async def get_max_tokens(self) -> int:
        """Получение максимального количества токенов в ответе из БД."""
        from bot.services.database import db
        val = await db.get_setting("max_tokens", "4096")
        return int(val)

    @property
    def websearch_enabled(self) -> bool:
        return bool(self.brave_api_key or self.tavily_api_key)

config = Config()
