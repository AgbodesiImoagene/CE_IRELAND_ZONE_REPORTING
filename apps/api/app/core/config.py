from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "dev"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    postgres_url: str = "postgresql+psycopg://app:app@db:5432/app"
    redis_url: str = "redis://redis:6379/0"

    s3_endpoint: str = "http://minio:9000"
    s3_bucket: str = "ce-exports"
    s3_access_key: str = "minio"
    s3_secret_key: str = "minio123"

    jwt_secret: str = "change-me"
    tenant_id: str = "12345678-1234-5678-1234-567812345678"
    tenant_name: str = "CE Ireland Zone"

    # OAuth SSO
    google_client_id: str = ""
    google_client_secret: str = ""
    facebook_client_id: str = ""
    facebook_client_secret: str = ""
    oauth_redirect_base_url: str = "http://localhost:8000/api/v1/auth/oauth"

    # RLS (Row-Level Security) toggle
    enable_rls: bool = True  # Set to False to disable RLS for testing/dev

    # Email configuration
    smtp_host: str = "localhost"
    smtp_port: int = 1025  # Default to MailHog/MailCatcher for dev
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@ce-ireland.zone"
    smtp_from_name: str = "CE Ireland Zone"

    # SMS configuration (for future implementation)
    sms_provider: str = ""  # twilio, aws-sns, etc.
    sms_api_key: str = ""
    sms_api_secret: str = ""
    sms_from_number: str = ""

    # Background job retry configuration
    max_notification_retries: int = 3  # Max retries for failed notifications

    # Middleware configuration
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    log_format: str = "json"  # json or text
    enable_request_logging: bool = True
    cors_origins: str = ""  # Comma-separated list of allowed origins
    enable_gzip: bool = True

    # Metrics configuration (OpenTelemetry)
    enable_metrics: bool = True  # Enable OpenTelemetry metrics
    metrics_namespace: str = ""  # OpenTelemetry meter name (defaults to tenant_name)
    otel_service_name: str = ""  # OpenTelemetry service name (defaults to tenant_name)
    otel_exporter_otlp_endpoint: str = ""  # OTLP endpoint (e.g., http://localhost:4317)

    # Rate limiting configuration
    enable_rate_limiting: bool = False  # Enable rate limiting
    rate_limit_window_seconds: int = 60  # Time window for rate limiting
    rate_limit_max_requests_per_ip: int = 100  # Max requests per IP per window
    rate_limit_max_requests_per_user: int = 1000  # Max requests per user per window

    # Slow connection rejection configuration
    enable_slow_connection_rejection: bool = False  # Reject slow connections
    slow_connection_timeout_seconds: float = 5.0  # Timeout in seconds

    model_config = {
        "env_file": "../.env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
