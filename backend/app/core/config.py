from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "HEALIX Emergency Information Interoperability"
    API_V1_STR: str = "/api"
    
    # Secret keys for JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "hc04-emergency-super-secret-jwt-key-2026-interop")
    JWT_REFRESH_SECRET: str = os.getenv("JWT_REFRESH_SECRET", "hc04-refresh-secret-key-emergency-2026")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database URL - defaults to SQLite for zero-dependency local testing, easily overridden by PostgreSQL
    # On Vercel serverless environments, default to /tmp/hc04.db because the root filesystem is read-only.
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:////tmp/hc04.db" if os.getenv("VERCEL") else "sqlite:///./hc04.db"
    )
    
    # CORS Origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*"
    ]
    
    # Upload directory
    UPLOAD_DIR: str = os.getenv(
        "UPLOAD_DIR",
        "/tmp/uploads" if os.getenv("VERCEL") else "./uploads"
    )
    
    # External EHR connector configurations (per requirement #52)
    FHIR_BASE_URL: str = os.getenv("FHIR_BASE_URL", "https://mock-hospital-fhir.hc04.internal/r4")
    FHIR_CLIENT_ID: str = os.getenv("FHIR_CLIENT_ID", "")
    FHIR_CLIENT_SECRET: str = os.getenv("FHIR_CLIENT_SECRET", "")
    
    HL7_ENDPOINT_HOST: str = os.getenv("HL7_ENDPOINT_HOST", "127.0.0.1")
    HL7_ENDPOINT_PORT: int = int(os.getenv("HL7_ENDPOINT_PORT", "2575"))
    
    # Emergency Break-Glass configuration
    EMERGENCY_SESSION_DURATION_MINUTES: int = 15
    
    # Development Seed flag
    AUTO_SEED: bool = True

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
