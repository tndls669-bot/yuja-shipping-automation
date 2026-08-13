"""일일 요약 메일 발송 — Gmail SMTP(앱 비밀번호) 사용."""
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from network_compat import force_ipv4

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 465


def send_summary_email(
    subject: str,
    body: str,
    gmail_address: str,
    app_password: str,
    to_addr: str = None,
    attachments: list[str] = None,
) -> None:
    force_ipv4()
    to_addr = to_addr or gmail_address

    if attachments:
        msg = MIMEMultipart()
        msg.attach(MIMEText(body, _charset="utf-8"))
        for path in attachments:
            with open(path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(path))
            part["Content-Disposition"] = f'attachment; filename="{os.path.basename(path)}"'
            msg.attach(part)
    else:
        msg = MIMEText(body, _charset="utf-8")

    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = to_addr

    with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT, timeout=20) as server:
        server.login(gmail_address, app_password)
        server.sendmail(gmail_address, [to_addr], msg.as_string())
