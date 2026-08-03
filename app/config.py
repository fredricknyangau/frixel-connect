from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Frixel Connect"
    APP_ENV: str = "development"
    DEBUG: bool = True
    ALLOWED_ORIGINS: list[str] = ["*"]
    TRUSTED_PROXIES: Optional[str] = None

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
    WIREGUARD_SERVER_PUBLIC_KEY: Optional[str] = "Frixel ConnectServerPublicKeyWgPlaceholderBase64="
    WIREGUARD_ENDPOINT: str = "102.219.208.5:51820"
    MOCK_WIREGUARD: bool = True

    # Magic Command-Production API base URL (used to build confirm_url in .rsc scripts)
    # Change this to your actual domain when deploying to production.
    API_BASE_URL: str = "https://api.Frixel Connect.dev"

    # Magic Command-CHR (VirtualBox) testing configuration
    # These settings are only used when is_chr=True is passed to /init-magic.
    # They define how the MikroTik CHR (running in VirtualBox) reaches the
    # Ubuntu host where the Frixel Connect backend is running.
    #
    # CHR_HOST_IP:          The Ubuntu host's IP on the VirtualBox host-only
    #                       adapter. Default: 192.168.56.1 (VirtualBox default).
    #                       If your VirtualBox adapter uses a different subnet,
    #                       change this to match your vboxnet0 IP.
    #
    # CHR_BACKEND_PORT:     The port FastAPI is listening on (uvicorn default: 8000).
    #
    # CHR_HOST_ONLY_NETWORK: The /24 network block for the firewall rule that
    #                         allows the backend to reach CHR's REST API.
    #                         Default: 192.168.56.0 (VirtualBox host-only default).
    CHR_HOST_IP: str = "192.168.56.1"
    CHR_BACKEND_PORT: int = 8000
    CHR_FRONTEND_URL: str = "http://192.168.56.1"
    CHR_HOST_ONLY_NETWORK: str = "192.168.56.0"

    # KRA eTIMS
    KRA_ETIMS_BASE_URL: str = "https://etims-api-sbx.kra.go.ke"
    KRA_ETIMS_USERNAME: Optional[str] = None
    KRA_ETIMS_PASSWORD: Optional[str] = None
    KRA_ETIMS_MOCK: bool = True

    # Africa's Talking
    AT_USERNAME: str = "sandbox"
    AT_API_KEY: str = "dummy_key"

    @property
    def DARAJA_BASE_URL(self) -> str:
        if self.DARAJA_ENVIRONMENT == "production":
            return "https://api.safaricom.co.ke"
        return "https://sandbox.safaricom.co.ke"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()