from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_NAME: str = "ZealSync WiFi Billing"
    APP_ENV: str = "development"
    DEBUG: bool = True
    ALLOWED_ORIGINS: list[str] = ["*"]

    # Database
    DATABASE_URL: str

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # M-Pesa Daraja
    DARAJA_CONSUMER_KEY: str
    DARAJA_CONSUMER_SECRET: str
    DARAJA_SHORTCODE: str
    DARAJA_PASSKEY: str
    DARAJA_CALLBACK_URL: str
    DARAJA_ENVIRONMENT: str = "sandbox"

    # MikroTik (global fallback -superseded by per-tenant router records in Phase 2)
    MIKROTIK_HOST: str
    MIKROTIK_PORT: int = 80
    MIKROTIK_USERNAME: str
    MIKROTIK_PASSWORD: str

    # Fernet symmetric encryption key for router passwords stored in the DB.
    # Generate once: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # NEVER commit this value to git. Inject via Docker secrets or secret manager.
    FERNET_SECRET_KEY: Optional[str] = None

    # Default tenant ID (the original single-tenant MLP seed data).
    # Created by migration 007. Used in tests and backfill scripts.
    DEFAULT_TENANT_ID: str = "aaaaaaaa-0000-0000-0000-000000000001"

    # Redis URL for background task queue
    REDIS_URL: str = "redis://redis:6379/0"

    # RADIUS
    RADIUS_COA_SECRET: str = "testing123"

    # WireGuard Settings
    WIREGUARD_SERVER_PUBLIC_KEY: Optional[str] = "zealsyncServerPublicKeyWgPlaceholderBase64="
    WIREGUARD_ENDPOINT: str = "102.219.208.5:51820"
    MOCK_WIREGUARD: bool = True

    # KRA eTIMS
    KRA_ETIMS_BASE_URL: str = "https://etims-api-sbx.kra.go.ke"
    KRA_ETIMS_USERNAME: Optional[str] = None
    KRA_ETIMS_PASSWORD: Optional[str] = None
    KRA_ETIMS_MOCK: bool = True

    @property
    def DARAJA_BASE_URL(self) -> str:
        if self.DARAJA_ENVIRONMENT == "production":
            return "https://api.safaricom.co.ke"
        return "https://sandbox.safaricom.co.ke"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()