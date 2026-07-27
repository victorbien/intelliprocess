"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Stage
    STAGE: str = "dev"
    LOG_LEVEL: str = "INFO"

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

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
