"""March 2026 monthly newsletter — first edition."""
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

SUBJECT = "YieldLife Monthly Update \u2014 March 2026"

INTRO = (
    "Welcome to the first YieldLife monthly update! YieldLife is a free "
    "analytics platform for Cardano DeFi &mdash; we track historical yield "
    "data across liquidity pools, farms, and lending markets from Minswap, "
    "SundaeSwap, WingRiders, and Liqwid so you can make decisions with full "
    "knowledge of the past."
)

UPDATES = [
    {
        "icon": "&#x1F4CA;",
        "title": "Redesigned Portfolio Cards",
        "description": (
            "Position cards now feature a clean 3-column layout with "
            "protocol-branded colors, making it easier to scan your LP and "
            "lending positions at a glance."
        ),
    },
    {
        "icon": "&#x1F4DC;",
        "title": "Deposit History Tracking",
        "description": (
            "YieldLife now scans your on-chain transaction history to detect "
            "deposits and withdrawals automatically, showing percentage "
            "changes so you can see how each position has evolved."
        ),
    },
    {
        "icon": "&#x1F50D;",
        "title": "Auto-Discovery of Pools &amp; Markets",
        "description": (
            "New Minswap liquidity pools and Liqwid lending markets are now "
            "detected automatically. WingRiders and Sundaedwap also have this feature."
            "USDCx pool APIs has been added by Sundaeswap and Liqwid, we're expecting Minswap and WingRiders soon."
            "Use caution and double check rates on protocols when viewing any new pools, including USDCx. We're building fast and live along side the protocols themselves."
            ""
        ),
    },
    {
        "icon": "&#x1F4B0;",
        "title": "Improved Pricing Accuracy",
        "description": (
            "We replaced our pricing backend with Minswap pool-derived prices "
            "and added Pyth Network as a primary ADA price source for more "
            "reliable valuations."
        ),
    },

    {
        "icon": "&#x26A1;",
        "title": "Faster Page Loads",
        "description": (
            "Compressed images, lazy-loaded logos, deferred chart scripts, and "
            "an optimized background video for a noticeably snappier experience."
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
            )
            if result:
                print("OK")
                sent += 1
            else:
                print("FAILED")
                failed += 1
            time.sleep(2)  # Brief pause to avoid SMTP rate limits

        print(f"\nDone! Sent: {sent}, Failed: {failed}")
