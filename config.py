import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Polymarket
    POLYMARKET_API_KEY: str = os.getenv("POLYMARKET_API_KEY", "")
    POLYMARKET_API_SECRET: str = os.getenv("POLYMARKET_API_SECRET", "")
    POLYMARKET_API_PASSPHRASE: str = os.getenv("POLYMARKET_API_PASSPHRASE", "")
    POLYMARKET_PRIVATE_KEY: str = os.getenv("POLYMARKET_PRIVATE_KEY", "")

    # Polygon
    POLYGON_RPC_URL: str = os.getenv(
        "POLYGON_RPC_URL",
        "https://polygon-rpc.com",
    )
    # USDC.e on Polygon
    USDC_CONTRACT: str = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

    # Anthropic
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = "claude-sonnet-4-6"

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Trading parameters
    EV_THRESHOLD: float = float(os.getenv("EV_THRESHOLD", "0.05"))
    KELLY_FRACTION: float = float(os.getenv("KELLY_FRACTION", "0.25"))
    MAX_SLIPPAGE: float = float(os.getenv("MAX_SLIPPAGE", "0.02"))
    MAX_POSITION_USD: float = float(os.getenv("MAX_POSITION_USD", "200"))
    SCAN_INTERVAL_SECONDS: int = int(os.getenv("SCAN_INTERVAL_SECONDS", "1800"))

    # Minimum liquidity volume to consider a market ($)
    MIN_MARKET_VOLUME: float = 50_000

    # Database
    DB_PATH: str = os.getenv("DB_PATH", "positions.db")

    # Logging
    LOG_DIR: str = "logs"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    def validate(self) -> None:
        required = {
            "POLYMARKET_PRIVATE_KEY": self.POLYMARKET_PRIVATE_KEY,
            "ANTHROPIC_API_KEY": self.ANTHROPIC_API_KEY,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")


config = Config()
