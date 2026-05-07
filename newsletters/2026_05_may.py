"""May 2026 monthly newsletter — third edition."""
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from flask import Flask
from flask_mail import Mail

app = Flask(__name__)
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
sender_email = os.environ.get('MAIL_DEFAULT_SENDER')
app.config['MAIL_DEFAULT_SENDER'] = ('YieldLife', sender_email)

mail = Mail(app)

SUBJECT = "YieldLife Monthly Update \u2014 May 2026"

INTRO = (
    "May brought a milestone for YieldLife &mdash; the frontend is now deployed on IPFS, "
    "making the site more resilient and decentralized. We\u2019ve also continued squashing "
    "edge cases in portfolio tracking as more wallets come through the door."
)

UPDATES = [
    {
        "icon": "&#x1F310;",
        "title": "Now on IPFS",
        "description": (
            "The YieldLife frontend is now hosted on IPFS via Filecoin and Pinata, meaning the "
            "site is permanently archived and accessible through the decentralized web. "
            "You can still reach us at yieldlife.xyz as always."
        ),
    },
    {
        "icon": "&#x1F47B;",
        "title": "Ghost Position Fixes",
        "description": (
            "Closed farm positions were occasionally reappearing after a full exit, and in some "
            "cases showing up twice. Both issues are resolved \u2014 your portfolio view should "
            "now accurately reflect only active positions."
        ),
    },
    {
        "icon": "&#x1F4CA;",
        "title": "Default Chart Improvements",
        "description": (
            "The Pools &amp; Farms page now defaults to more relevant pairs (USDA/ADA, USDM/ADA) "
            "so you land on meaningful data right away."
        ),
    },
    {
        "icon": "&#x1F6E1;",
        "title": "Dependency Updates",
        "description": (
            "Upgraded psycopg2, pandas, and several other dependencies to stay current with "
            "Python 3.13 and address security alerts."
        ),
    },
]

BASE_URL = "https://yieldlife.xyz"

# --- Send ---
if __name__ == "__main__":
    # Set to True to send to all DB subscribers, False for test mode
    SEND_TO_ALL = True
    TEST_RECIPIENT = "danladuke@michigantokenizers.com"

    import time

    print(f"MAIL_SERVER: {app.config['MAIL_SERVER']}")
    print(f"MAIL_PORT:   {app.config['MAIL_PORT']}")
    print(f"MAIL_SENDER: {app.config['MAIL_DEFAULT_SENDER']}")
    print()

    if SEND_TO_ALL:
        from src.database.connection import DatabaseConnection
        db = DatabaseConnection()
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT email FROM users WHERE email IS NOT NULL ORDER BY email")
                emails = [row[0] for row in cur.fetchall()]
        finally:
            db.return_connection(conn)

        print(f"Found {len(emails)} email addresses:")
        for e in emails:
            print(f"  - {e}")
        print()

        confirm = input(f"Send newsletter to all {len(emails)} recipients? (yes/no): ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            sys.exit(0)
    else:
        emails = [TEST_RECIPIENT]
        print(f"TEST MODE: sending to {TEST_RECIPIENT} only")
        print()

    with app.app_context():
        import src.auth.email as email_module
        email_module.mail = mail

        from src.auth.email import send_newsletter_email

        sent = 0
        failed = 0
        for email in emails:
            print(f"Sending to {email}...", end=" ")
            result = send_newsletter_email(
                to_email=email,
                base_url=BASE_URL,
                subject=SUBJECT,
                intro=INTRO,
                updates=UPDATES,
                month_label="May 2026",
                banner_image="lake-michigan-aura.jpg",
                photo_credit_url="https://leah-may.pixels.com/featured/lake-michigan-aura-leah-may.html",
            )
            if result:
                print("OK")
                sent += 1
            else:
                print("FAILED")
                failed += 1
            time.sleep(2)  # Brief pause to avoid SMTP rate limits

        print(f"\nDone! Sent: {sent}, Failed: {failed}")
