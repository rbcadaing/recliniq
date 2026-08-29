from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://recliniq:recliniq@localhost:5432/recliniq"
    jwt_secret: str = "dev-only-change-me-use-32bytes-min"
    jwt_expire_minutes: int = 60 * 24
    cors_origins: str = "http://localhost:5173"
    upload_dir: str = "./uploads"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@example.com"
    seed_tenant_name: str = "Demo Clinic"
    seed_tenant_tz: str = "Asia/Manila"
    seed_doctor_email: str = "doctor@example.com"
    seed_doctor_password: str = "DoctorPass1!"
    seed_assistant_email: str = "assistant@example.com"
    seed_assistant_password: str = "AssistPass1!"
    slot_minutes: int = 30

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
