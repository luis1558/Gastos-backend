from __future__ import annotations

from dataclasses import dataclass

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from app.core.config import settings


@dataclass
class ReminderEmailData:
    user_email: str
    user_name: str
    debt_description: str
    counterparty_name: str
    original_amount: str
    paid_amount: str
    remaining_amount: str
    due_date: str
    reminder_type_label: str


conf = ConnectionConfig(
    MAIL_USERNAME=settings.smtp_user,
    MAIL_PASSWORD=settings.smtp_password,
    MAIL_FROM=settings.smtp_from_email,
    MAIL_PORT=settings.smtp_port,
    MAIL_SERVER=settings.smtp_host,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
)

fm = FastMail(conf)

REMINDER_SUBJECTS = {
    "seven_days": "Recordatorio: Deuda por vencer en 7 días",
    "three_days": "Recordatorio: Deuda por vencer en 3 días",
    "due_date": "¡Vence hoy! Deuda pendiente",
}

REMINDER_LABELS = {
    "seven_days": "7 días antes del vencimiento",
    "three_days": "3 días antes del vencimiento",
    "due_date": "Vence hoy",
}


def _build_html(data: ReminderEmailData) -> str:
    return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;background:#f4f4f5;margin:0;padding:0">
  <table style="max-width:560px;margin:0 auto;padding:24px">
    <tr><td style="background:#4f46e5;border-radius:12px 12px 0 0;padding:24px;text-align:center">
      <h1 style="color:#fff;margin:0;font-size:20px">📌 {data.reminder_type_label}</h1>
    </td></tr>
    <tr><td style="background:#fff;border-radius:0 0 12px 12px;padding:24px">
      <p style="color:#374151;font-size:14px;margin:0 0 16px">Hola <strong>{data.user_name}</strong>,</p>
      <p style="color:#374151;font-size:14px;margin:0 0 20px">
        Tienes una deuda próxima a vencer. Aquí están los detalles:
      </p>

      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <tr><td style="padding:8px 12px;color:#6b7280">Descripción</td>
            <td style="padding:8px 12px;font-weight:600;text-align:right">{data.debt_description}</td></tr>
        <tr style="background:#f9fafb"><td style="padding:8px 12px;color:#6b7280">Contraparte</td>
            <td style="padding:8px 12px;font-weight:600;text-align:right">{data.counterparty_name}</td></tr>
        <tr><td style="padding:8px 12px;color:#6b7280">Monto original</td>
            <td style="padding:8px 12px;font-weight:600;text-align:right">{data.original_amount}</td></tr>
        <tr style="background:#f9fafb"><td style="padding:8px 12px;color:#6b7280">Pagado</td>
            <td style="padding:8px 12px;font-weight:600;text-align:right;color:#059669">{data.paid_amount}</td></tr>
        <tr><td style="padding:8px 12px;color:#6b7280">Saldo pendiente</td>
            <td style="padding:8px 12px;font-weight:600;text-align:right;color:#dc2626">{data.remaining_amount}</td></tr>
        <tr style="background:#f9fafb"><td style="padding:8px 12px;color:#6b7280">Vencimiento</td>
            <td style="padding:8px 12px;font-weight:600;text-align:right">{data.due_date}</td></tr>
      </table>

      <p style="color:#6b7280;font-size:12px;margin-top:20px;text-align:center">
        Este es un mensaje automático de <strong>Gastos App</strong>.
      </p>
    </td></tr>
  </table>
</body>
</html>"""


async def send_reminder_email(data: ReminderEmailData, reminder_type: str) -> None:
    html = _build_html(data)
    message = MessageSchema(
        subject=REMINDER_SUBJECTS.get(reminder_type, "Recordatorio de deuda"),
        recipients=[data.user_email],
        body=html,
        subtype=MessageType.html,
    )
    await fm.send_message(message)
