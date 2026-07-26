import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Banco de dados. Em produção (Railway/Render), defina DATABASE_URL apontando
    # para o Postgres fornecido pela plataforma. Em desenvolvimento local, cai
    # para um arquivo SQLite.
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./revela.db")

    # Segredo usado para assinar os tokens JWT. TROQUE em produção.
    jwt_secret: str = os.getenv("JWT_SECRET", "troque-este-segredo-em-producao")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

    # Onde as imagens ficam salvas em disco. Em produção, aponte para um volume
    # persistente (ex: /app/media no Railway com um Volume anexado), senão as
    # fotos somem a cada novo deploy.
    media_root: str = os.getenv("MEDIA_ROOT", "./media")

    # Texto da marca d'água aplicada em toda foto de pré-visualização.
    watermark_text: str = os.getenv("WATERMARK_TEXT", "REVELA · PROVA")

    # Tamanho máximo (lado maior, em pixels) das imagens de pré-visualização
    # (baixa resolução) mostradas para clientes.
    preview_max_dimension: int = int(os.getenv("PREVIEW_MAX_DIMENSION", "1000"))
    preview_jpeg_quality: int = int(os.getenv("PREVIEW_JPEG_QUALITY", "70"))

    # Quanto MENOR, mais rígida a comparação facial (menos falsos positivos,
    # mas pode deixar de encontrar fotos em ângulos ruins). 0.6 é o padrão
    # recomendado pela biblioteca face_recognition.
    face_match_tolerance: float = float(os.getenv("FACE_MATCH_TOLERANCE", "0.6"))

    # Origens permitidas para chamadas do frontend (separadas por vírgula).
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")

    # SMTP para o e-mail de "esqueci minha senha". Se smtp_host ficar vazio,
    # o link de redefinição só é impresso no log (ok pra teste, não pra
    # produção — configure um provedor de verdade, ex: Gmail, SendGrid, Resend).
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from: str = os.getenv("SMTP_FROM", "")
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    class Config:
        env_file = ".env"


settings = Settings()
