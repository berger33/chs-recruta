from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from .config import get_settings


def send_password_reset_email(recipient: str, display_name: str, reset_url: str) -> bool:
    """Entrega síncrona mínima; produção pode substituir por worker sem mudar o domínio."""
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from:
        return False
    message = EmailMessage()
    message["Subject"] = "Redefinição de senha — CHS RH"
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message.set_content(
        f"Olá, {display_name}.\n\n"
        "Recebemos uma solicitação para redefinir sua senha. "
        f"Use este link único e temporário:\n{reset_url}\n\n"
        "Se você não solicitou a alteração, ignore esta mensagem e avise o administrador."
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
        if settings.smtp_starttls:
            client.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password)
        client.send_message(message)
    return True


def safely_send_password_reset_email(
    recipient: str, display_name: str, reset_url: str
) -> None:
    """Background tasks must never turn SMTP failure into an auth response leak."""
    try:
        send_password_reset_email(recipient, display_name, reset_url)
    except Exception:
        # A operação fica observável como enfileirada; monitoramento SMTP deve
        # alertar a equipe sem revelar o estado da conta ao solicitante.
        return
