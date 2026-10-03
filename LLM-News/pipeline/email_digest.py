"""Email the daily digest (overview, highlights and linked headlines) to a list of readers.

    python pipeline/email_digest.py                 # latest edition
    python pipeline/email_digest.py --date 2026-10-02
    python pipeline/email_digest.py --dry-run       # save the email as a .eml file instead of sending

Settings (.env): SMTP_HOST, SMTP_PORT (default 587, STARTTLS), SMTP_USER, SMTP_PASSWORD, SMTP_FROM,
DIGEST_EMAIL_TO (comma-separated), PUBLIC_BASE_URL (for article links). Without SMTP_HOST it only saves
the .eml file. The digest comes from a running backend (BACKEND_URL, default http://127.0.0.1:8000).
"""
import argparse
import json
import os
import smtplib
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from email.message import EmailMessage
from html import escape
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def fetch(backend: str, path: str):
    with urllib.request.urlopen(backend.rstrip("/") + path, timeout=300) as response:
        return json.load(response)


def text_items(value) -> list:
    """LLM output as lines: "text", ["a", "b"] or {"k": "v"}"""
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [t for v in value for t in text_items(v)]
    if isinstance(value, dict):
        return [t for v in value.values() for t in text_items(v)]
    return []


def build_email(digest: dict, news: list, site: str) -> EmailMessage:
    day = datetime.strptime(digest["date"], "%Y-%m-%d").strftime("%A %d %B %Y")
    link_for = {item["headline"]: f"{site}/article/{item['date']}/{item['group_id']}" for item in news}
    overview = " ".join(text_items(digest.get("digest")))
    highlights = text_items(digest.get("highlights"))
    sections = [(category, info.get("headlines", [])) for category, info in (digest.get("category_breakdown") or {}).items()]

    plain = [f"NewsSense daily digest - {day}", "", overview, ""]
    plain += ["Top highlights:"] + [f"{n}. {h}" for n, h in enumerate(highlights, 1)] + [""]
    for category, headlines in sections:
        plain.append(category.capitalize() + ":")
        plain += [f"- {h}  {link_for.get(h, '')}".rstrip() for h in headlines]
        plain.append("")
    plain.append(f"Every story links to its original sources: {site}/")

    html = [f"<h1 style='font-family:Georgia,serif'>NewsSense &middot; {escape(day)}</h1>",
            f"<p style='font-size:17px;line-height:1.6'>{escape(overview)}</p>"]
    if highlights:
        html.append("<h2>Top highlights</h2><ol>" + "".join(f"<li>{escape(h)}</li>" for h in highlights) + "</ol>")
    for category, headlines in sections:
        items = "".join(
            f"<li><a href='{escape(link_for[h])}'>{escape(h)}</a></li>" if h in link_for else f"<li>{escape(h)}</li>"
            for h in headlines
        )
        html.append(f"<h2>{escape(category.capitalize())}</h2><ul>{items}</ul>")
    html.append(f"<p style='color:#666'>AI-written from public news reports. Every story links to its sources: "
                f"<a href='{escape(site)}/'>{escape(site)}</a></p>")

    message = EmailMessage()
    message["Subject"] = f"Your NewsSense digest for {day}"
    message["From"] = os.getenv("SMTP_FROM") or os.getenv("SMTP_USER") or "newssense@localhost"
    message["To"] = os.getenv("DIGEST_EMAIL_TO", "")
    message.set_content("\n".join(plain))
    message.add_alternative("<html><body style='max-width:640px'>" + "".join(html) + "</body></html>", subtype="html")
    return message


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--date", help="edition date (default: latest)")
    parser.add_argument("--backend-url", default=os.getenv("BACKEND_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--dry-run", action="store_true", help="save the email instead of sending it")
    args = parser.parse_args()

    date = args.date or (fetch(args.backend_url, "/api/news/dates?limit=1")["dates"] or [None])[0]
    if not date:
        sys.exit("No news has been generated yet.")
    digest = fetch(args.backend_url, f"/api/digest/daily/{urllib.parse.quote(date)}")
    if digest.get("error") or not digest.get("total_articles"):
        sys.exit(f"No digest available for {date}: {digest.get('digest', '')}")
    news = fetch(args.backend_url, f"/api/news?date={urllib.parse.quote(date)}")
    site = (os.getenv("PUBLIC_BASE_URL") or "http://localhost:5173").rstrip("/")
    message = build_email(digest, news, site)

    recipients = [r.strip() for r in os.getenv("DIGEST_EMAIL_TO", "").split(",") if r.strip()]
    if args.dry_run or not os.getenv("SMTP_HOST") or not recipients:
        out = ROOT / "data" / "output" / f"digest-{date}.eml"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(bytes(message))
        reason = "dry run" if args.dry_run else "SMTP_HOST or DIGEST_EMAIL_TO not set"
        print(f"Not sent ({reason}). Saved the email to {out}")
        return

    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587")), timeout=60) as smtp:
        smtp.starttls()
        if os.getenv("SMTP_USER"):
            smtp.login(os.environ["SMTP_USER"], os.getenv("SMTP_PASSWORD", ""))
        smtp.send_message(message, to_addrs=recipients)
    print(f"Sent the {date} digest to {len(recipients)} recipient(s).")


if __name__ == "__main__":
    main()
