"""
Email notifications via Gmail SMTP.
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import defaultdict


RECIPIENT = "lukasbar1994@gmail.com"
BOOKING_URL = "https://openresa.com/reservation"


def _send(subject: str, body_text: str, body_html: str) -> None:
    sender = os.environ["GMAIL_ADDRESS"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = RECIPIENT
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, app_password)
        smtp.sendmail(sender, RECIPIENT, msg.as_string())


def _group_by_day(slots: list[dict]) -> dict:
    """Group slots by date_label, then by court."""
    by_day = defaultdict(lambda: defaultdict(list))
    for s in slots:
        by_day[s["date_label"]][s["court"]].append(s["time_str"])
    return by_day


def send_weekly_overview(slots: list[dict]) -> None:
    """Send the Thursday overview email with all weekend availability."""
    subject = "TC Sweet Spot – Weekend Court Availability (18–21h)"

    if not slots:
        text_body = (
            "Hi Lukas,\n\n"
            "No courts available on Friday, Saturday, or Sunday between 18:00 and 21:00.\n\n"
            f"Check manually: {BOOKING_URL}\n"
        )
        html_body = f"""
        <p>Hi Lukas,</p>
        <p>No courts are available on Friday, Saturday, or Sunday between 18:00 and 21:00.</p>
        <p><a href="{BOOKING_URL}">Check manually on openresa.com</a></p>
        """
    else:
        by_day = _group_by_day(slots)
        text_lines = ["Hi Lukas,", "", "Weekend court availability at TC Sweet Spot (18:00–21:00):", ""]
        html_sections = ["<p>Hi Lukas,</p>", "<p>Weekend court availability at TC Sweet Spot (18:00–21:00):</p>"]

        for day_label, courts in by_day.items():
            text_lines.append(f"  {day_label.upper()}")
            html_sections.append(f"<h3>{day_label}</h3><ul>")
            for court in ["Court 1", "Court 2", "Court 3"]:
                times = sorted(courts.get(court, []))
                if times:
                    times_str = ", ".join(times)
                    text_lines.append(f"    {court}: {times_str}")
                    html_sections.append(f"<li><strong>{court}</strong>: {times_str}</li>")
                else:
                    text_lines.append(f"    {court}: –")
            text_lines.append("")
            html_sections.append("</ul>")

        text_lines += [f"Book here: {BOOKING_URL}"]
        html_sections.append(f'<p><a href="{BOOKING_URL}">Book on openresa.com</a></p>')

        text_body = "\n".join(text_lines)
        html_body = "\n".join(html_sections)

    _send(subject, text_body, html_body)
    print(f"Weekly overview email sent ({len(slots)} slots)")


def send_new_slot_alert(new_slots: list[dict]) -> None:
    """Send an alert email for newly opened slots."""
    if not new_slots:
        return

    count = len(new_slots)
    subject = f"New Slot{'s' if count > 1 else ''} Available – TC Sweet Spot"

    by_day = _group_by_day(new_slots)
    text_lines = ["Hi Lukas,", "", f"{count} new slot{'s' if count > 1 else ''} just opened at TC Sweet Spot:", ""]
    html_sections = [
        "<p>Hi Lukas,</p>",
        f"<p><strong>{count} new slot{'s' if count > 1 else ''}</strong> just opened at TC Sweet Spot:</p>",
    ]

    for day_label, courts in by_day.items():
        text_lines.append(f"  {day_label.upper()}")
        html_sections.append(f"<h3>{day_label}</h3><ul>")
        for court, times in sorted(courts.items()):
            for t in sorted(times):
                text_lines.append(f"    {court}: {t}")
                html_sections.append(f"<li><strong>{court}</strong>: {t}</li>")
        text_lines.append("")
        html_sections.append("</ul>")

    text_lines += [f"Book here: {BOOKING_URL}"]
    html_sections.append(f'<p><a href="{BOOKING_URL}">Book now on openresa.com</a></p>')

    text_body = "\n".join(text_lines)
    html_body = "\n".join(html_sections)

    _send(subject, text_body, html_body)
    print(f"Alert email sent for {count} new slot(s)")
