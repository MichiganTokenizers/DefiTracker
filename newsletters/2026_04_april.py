"""April 2026 monthly newsletter — second edition."""
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

SUBJECT = "YieldLife Monthly Update \u2014 April 2026"

INTRO = (
    "This month\u2019s focus has been data quality. Rather than rushing to add features, "
    "we\u2019ve been going deep on accuracy &mdash; validating that what you\u2019re seeing "
    "reflects reality. We found and fixed two notable issues, cleaned up the affected data, "
    "and have been running cleanly and consistently for the last couple of weeks."
)

UPDATES = [
    {
        "icon": "&#x1F551;",
        "title": "Timezone Bug Fixed",
        "description": (
            "Our database server running in BST was causing duplicate snapshots to be recorded "
            "around daylight saving transitions. Fixed and historical data has been corrected."
        ),
    },
    {
        "icon": "&#x1F4CA;",
        "title": "Minswap TVL Undercount Resolved",
        "description": (
            "The yield server was returning incomplete TVL figures for certain Minswap pools, "
            "which was inflating APR calculations. We\u2019ve patched the source and backfilled "
            "the affected data."
        ),
    },
    {
        "icon": "&#x26A1;",
        "title": "SundaeSwap Reliability",
        "description": (
            "Added retry logic and per-position error handling for SundaeSwap. Failures on "
            "individual positions no longer cause the whole fetch to bail out."
        ),
    },
    {
        "icon": "&#x1F5C2;",
        "title": "Improved Charts & UI",
        "description": (
            "Saved charts dropdown redesigned with badges and asset details. Pool version labels "
            "now display correctly for stableswaps, and charts default more sensibly for "
            "lending and single-asset views."
        ),
    },
    {
        "icon": "&#x1F6E3;",
        "title": "On the Horizon",
        "description": (
            "Two things are coming up: an infrastructure upgrade to handle more wallets and "
            "higher data frequency, and early work on a public API so you can pull historical "
            "APR and TVL data for your own use. More details next month."
        ),
    },
]

BASE_URL = "https://yieldlife.xyz"

# --- Send ---
if __name__ == "__main__":
    # Set to True to send to all DB subscribers, False for test mode
    SEND_TO_ALL = False
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
                month_label="April 2026",
                banner_image="morning_dew_white_rabbit.jpg",
                photo_credit_url="https://fineartamerica.com/profiles/leah-may",
            )
            if result:
                print("OK")
                sent += 1
            else:
                print("FAILED")
                failed += 1
            time.sleep(2)  # Brief pause to avoid SMTP rate limits

        print(f"\nDone! Sent: {sent}, Failed: {failed}")
