import html
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv


SRC_DIR = Path(__file__).resolve().parent

load_dotenv(dotenv_path=SRC_DIR / ".env")

ALERT_RISK_CLASSES = {"Caution", "Dangerous"}


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def format_percent(value):
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "--"


def format_value(value, unit=""):
    if value is None:
        return "--"
    return f"{value}{unit}"


def alert_recommendation(result):
    return (
        result.get("llm_action_recommendation")
        or result.get("llm_recommendation")
        or result.get("action_recommendation")
        or "No recommendation was generated."
    )


def build_subject(result):
    risk_class = result.get("risk_class", "Alert")
    device_id = result.get("device_id", "unknown device")

    if risk_class == "Dangerous":
        return f"[DANGEROUS] OmiGuard Gas Risk Alert - Immediate Action Required ({device_id})"

    return f"[CAUTION] OmiGuard Gas Risk Alert - Elevated Risk Detected ({device_id})"


def build_plain_text(result):
    sensor = result.get("sensor_data") or {}
    recommendation = alert_recommendation(result)
    dashboard_url = os.getenv("ALERT_DASHBOARD_URL", "").strip()

    lines = [
        "OmiGuard Safety Alert",
        "",
        f"Risk level: {result.get('risk_class', '--')}",
        f"Device: {result.get('device_id', '--')}",
        f"Prediction time: {result.get('prediction_time', '--')}",
        f"Sensor time: {result.get('sensor_timestamp', '--')}",
        f"Risk score: {format_percent(result.get('risk_score'))}",
        f"Anomaly: {'Detected' if result.get('anomaly_flag') else 'Clear'}",
        "",
        "Key readings:",
        f"- CO: {format_value(sensor.get('co'), ' ppm')}",
        f"- SO2: {format_value(sensor.get('so2'), ' ppm')}",
        f"- NO2: {format_value(sensor.get('no2'), ' ppm')}",
        f"- PM2.5: {format_value(sensor.get('pm2_5'), ' ug/m3')}",
        f"- PM10: {format_value(sensor.get('pm10'), ' ug/m3')}",
        f"- Temperature: {format_value(sensor.get('temperature'), ' C')}",
        f"- Humidity: {format_value(sensor.get('humidity'), '%')}",
        "",
        "LLM recommendation:",
        recommendation,
    ]

    if dashboard_url:
        lines.extend(["", f"Dashboard: {dashboard_url}"])

    return "\n".join(lines)


def build_html(result):
    sensor = result.get("sensor_data") or {}
    risk_class = result.get("risk_class", "--")
    recommendation = alert_recommendation(result)
    dashboard_url = os.getenv("ALERT_DASHBOARD_URL", "").strip()
    color = "#d92d20" if risk_class == "Dangerous" else "#f79009"
    soft_color = "#fff1f0" if risk_class == "Dangerous" else "#fff7e6"

    rows = [
        ("CO", format_value(sensor.get("co"), " ppm")),
        ("SO2", format_value(sensor.get("so2"), " ppm")),
        ("NO2", format_value(sensor.get("no2"), " ppm")),
        ("PM2.5", format_value(sensor.get("pm2_5"), " ug/m3")),
        ("PM10", format_value(sensor.get("pm10"), " ug/m3")),
        ("Temperature", format_value(sensor.get("temperature"), " C")),
        ("Humidity", format_value(sensor.get("humidity"), "%")),
    ]
    row_html = "".join(
        f"<tr><td>{html.escape(label)}</td><td><strong>{html.escape(value)}</strong></td></tr>"
        for label, value in rows
    )
    dashboard_link = (
        f'<p><a href="{html.escape(dashboard_url)}" style="color:#064e45;font-weight:700;">Open OmiGuard dashboard</a></p>'
        if dashboard_url
        else ""
    )

    return f"""\
<!doctype html>
<html>
  <body style="margin:0;background:#f4f2f8;font-family:Arial,sans-serif;color:#2f2b3d;">
    <div style="max-width:680px;margin:0 auto;padding:24px;">
      <div style="background:#ffffff;border-radius:8px;border:1px solid #e7e3ee;overflow:hidden;">
        <div style="background:{color};color:#ffffff;padding:18px 22px;">
          <p style="margin:0;font-size:13px;font-weight:700;letter-spacing:.03em;">OMIGUARD SAFETY ALERT</p>
          <h1 style="margin:8px 0 0;font-size:24px;line-height:1.2;">{html.escape(risk_class)} gas risk detected</h1>
        </div>
        <div style="padding:22px;">
          <div style="background:{soft_color};border-left:4px solid {color};padding:14px 16px;margin-bottom:18px;">
            <p style="margin:0;font-size:15px;"><strong>LLM recommendation:</strong></p>
            <p style="margin:8px 0 0;font-size:15px;line-height:1.5;">{html.escape(recommendation)}</p>
          </div>
          <table style="width:100%;border-collapse:collapse;margin-bottom:18px;">
            <tr><td>Device</td><td><strong>{html.escape(str(result.get("device_id", "--")))}</strong></td></tr>
            <tr><td>Prediction time</td><td><strong>{html.escape(str(result.get("prediction_time", "--")))}</strong></td></tr>
            <tr><td>Sensor time</td><td><strong>{html.escape(str(result.get("sensor_timestamp", "--")))}</strong></td></tr>
            <tr><td>Risk score</td><td><strong>{html.escape(format_percent(result.get("risk_score")))}</strong></td></tr>
            <tr><td>Anomaly</td><td><strong>{"Detected" if result.get("anomaly_flag") else "Clear"}</strong></td></tr>
          </table>
          <h2 style="font-size:17px;margin:0 0 10px;">Key readings</h2>
          <table style="width:100%;border-collapse:collapse;">{row_html}</table>
          {dashboard_link}
          <p style="margin-top:18px;color:#7b758c;font-size:12px;">This alert was generated automatically by OmiGuard.</p>
        </div>
      </div>
    </div>
  </body>
</html>
"""


def send_email(subject, text_body, html_body):
    host = os.getenv("SMTP_HOST")
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("ALERT_FROM_EMAIL") or username
    from_name = os.getenv("ALERT_FROM_NAME", "OmiGuard Alerts")
    to_emails = [
        email.strip()
        for email in os.getenv("ALERT_TO_EMAIL", "").split(",")
        if email.strip()
    ]
    port = env_int("SMTP_PORT", 587)
    use_ssl = env_bool("SMTP_USE_SSL", False)
    use_tls = env_bool("SMTP_USE_TLS", not use_ssl)

    if not all([host, username, password, from_email]) or not to_emails:
        raise ValueError("Email alert settings are incomplete. Check SMTP_* and ALERT_* values in .env.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{from_name} <{from_email}>"
    message["To"] = ", ".join(to_emails)
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=30) as server:
            server.login(username, password)
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            if use_tls:
                server.starttls()
            server.login(username, password)
            server.send_message(message)

    return {
        "subject": subject,
        "from_name": from_name,
        "from_email": from_email,
        "to_emails": to_emails,
        "sent_at": datetime.now().isoformat(timespec="seconds"),
    }


def send_risk_alert_if_needed(result):
    if not env_bool("ALERT_EMAIL_ENABLED", False):
        return False

    if result.get("risk_class") not in ALERT_RISK_CLASSES:
        return False

    subject = build_subject(result)
    try:
        alert_info = send_email(subject, build_plain_text(result), build_html(result))
        print(f"Email alert sent: {subject}")
        return alert_info
    except Exception as exc:
        print(f"Email alert failed: {exc}")
        return None
