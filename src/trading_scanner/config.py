"""
Configuración del sistema de trading scanner.

Variables de entorno via Pydantic Settings.
Nunca hardcodear valores - siempre vienen de .env o de la variable de entorno.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Turso — base de datos cloud (obligatorio)
    turso_database_url: str = ""
    turso_auth_token: str = ""

    # Schwab API (obligatorio)
    schwab_app_key: str = ""
    schwab_app_secret: str = ""
    schwab_callback_url: str = "https://127.0.0.1"

    # Trading Calendar — URL base (default localhost)
    calendar_base_url: str = "http://localhost:8000"

    # Puerto del scanner
    scanner_port: int = 8001

    # Carpeta de input para CSV de ToS
    input_folder: str = "./input"

    # Cache local de datos históricos para backtesting
    backtest_data_path: Path = Path("./backtest_data")

    # Modo mock: genera datos OHLCV sintéticos sin necesitar Schwab
    mock_schwab: bool = False


# Instancia singleton - se importa en toda la app
settings = Settings()
