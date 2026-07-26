"""
Envio de e-mail via SMTP. Usado hoje só para o link de redefinição de senha.

Se as variáveis SMTP_* não estiverem configuradas, a mensagem é apenas
registrada no log (Deploy Logs do Railway) em vez de enviada de verdade —
assim o fluxo não quebra em ambiente de teste, mas também não finge que
enviou um e-mail que na prática não saiu do servidor. Pra funcionar de
verdade em produção, configure um provedor SMTP (ver README).
"""
import smtplib
from email.mime.text import MIMEText

from .config import settings


def send_email(to_email: str, subject: str, body: str) -> bool:
    if not settings.smtp_host or not to_email:
        print(f"[REVELA] SMTP não configurado (ou sem e-mail cadastrado) — mensagem não enviada.\n"
              f"Para: {to_email}\nAssunto: {subject}\n{body}")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to_email

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(msg["From"], [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"[REVELA] Falha ao enviar e-mail para {to_email}: {e}")
        return False
