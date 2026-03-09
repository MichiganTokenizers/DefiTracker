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
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

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
    recipient = "danladuke@michigantokenizers.com"

    print(f"MAIL_SERVER: {app.config['MAIL_SERVER']}")
    print(f"MAIL_PORT:   {app.config['MAIL_PORT']}")
    print(f"MAIL_SENDER: {app.config['MAIL_DEFAULT_SENDER']}")
    print()

    with app.app_context():
        import src.auth.email as email_module
        email_module.mail = mail

        from src.auth.email import send_newsletter_email

        print(f"Sending to {recipient}...")
        result = send_newsletter_email(
            to_email=recipient,
            base_url=BASE_URL,
            subject=SUBJECT,
            intro=INTRO,
            updates=UPDATES,
        )
        if result:
            print("Sent successfully! Check your inbox.")
        else:
            print("Failed to send. Check error above.")
