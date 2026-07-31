"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings

# Locate .env in the project root (one level above this package)
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    # Stage
    STAGE: str = "dev"
    LOG_LEVEL: str = "INFO"
    USE_MOCKS: bool = True

    # AWS
    AWS_REGION: str = "us-east-1"

    # S3
    DOCUMENT_BUCKET: str = ""

    # DynamoDB Tables
    INVOICE_TABLE: str = ""
    PO_TABLE: str = ""
    GR_TABLE: str = ""
    CONVERSATION_TABLE: str = ""
    DOCUMENT_TABLE: str = ""

    # Amazon Bedrock
    BEDROCK_MODEL_ID: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    KNOWLEDGE_BASE_ID: str = ""
    GUARDRAIL_ID: str = ""

    # Bedrock Data Automation
    BDA_PROJECT_ARN: str = ""

    # Cognito
    COGNITO_USER_POOL_ID: str = ""
    COGNITO_APP_CLIENT_ID: str = ""

    model_config = {
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()
