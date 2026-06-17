from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "WiFi Billing System"
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

    # MikroTik
    MIKROTIK_HOST: str
    MIKROTIK_PORT: int = 80
    MIKROTIK_USERNAME: str
    MIKROTIK_PASSWORD: str

    @property
    def DARAJA_BASE_URL(self) -> str:
        if self.DARAJA_ENVIRONMENT == "production":
            return "https://api.safaricom.co.ke"
        return "https://sandbox.safaricom.co.ke"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()