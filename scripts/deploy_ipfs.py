#!/usr/bin/env python3
"""
Pin the dist/ directory to IPFS + Filecoin via Lighthouse.storage.

After uploading, prints the CID and the DNS TXT record to update.
Optionally auto-updates Cloudflare DNS if credentials are configured.

Usage (from project root):
    python scripts/deploy_ipfs.py

Required environment variables (in .env or shell):
    LIGHTHOUSE_API_KEY   API key from https://lighthouse.storage (free tier)

Optional environment variables for Cloudflare DNS auto-update:
    CLOUDFLARE_API_TOKEN  Cloudflare API token with DNS:Edit permission
    CLOUDFLARE_ZONE_ID    Zone ID for your domain (from Cloudflare dashboard)
    DNSLINK_SUBDOMAIN     Subdomain to update (default: app.yieldlife.io)
"""

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# ── Config ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"

load_dotenv(PROJECT_ROOT / ".env")

LIGHTHOUSE_API_KEY = os.environ.get("LIGHTHOUSE_API_KEY", "")
LIGHTHOUSE_UPLOAD_URL = "https://node.lighthouse.storage/api/v0/add"

CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
CLOUDFLARE_ZONE_ID = os.environ.get("CLOUDFLARE_ZONE_ID", "")
DNSLINK_SUBDOMAIN = os.environ.get("DNSLINK_SUBDOMAIN", "app.yieldlife.xyz")


# ── Upload ────────────────────────────────────────────────────────────────────

def upload_to_lighthouse(dist_dir: Path) -> str:
    """Upload dist/ directory to Lighthouse and return the root CID."""
    if not LIGHTHOUSE_API_KEY:
        print("ERROR: LIGHTHOUSE_API_KEY not set.")
        print("  Get a free key at https://lighthouse.storage")
        print("  Then add to .env:  LIGHTHOUSE_API_KEY=your_key_here")
        sys.exit(1)

    if not dist_dir.exists():
        print(f"ERROR: {dist_dir} not found. Run export_static.py first.")
        sys.exit(1)

    print(f"Uploading {dist_dir} to Lighthouse.storage ...")

    # Collect all files as multipart form data
    files = []
    for path in sorted(dist_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(dist_dir)
            files.append(
                ("file", (str(rel), open(path, "rb"), "application/octet-stream"))
            )

    print(f"  {len(files)} files to upload ...")

    resp = requests.post(
        LIGHTHOUSE_UPLOAD_URL,
        headers={"Authorization": f"Bearer {LIGHTHOUSE_API_KEY}"},
        files=files,
        timeout=300,
    )

    # Close all file handles
    for _, (_, fh, _) in files:
        fh.close()

    if not resp.ok:
        print(f"ERROR: Upload failed ({resp.status_code}): {resp.text}")
        sys.exit(1)

    # Lighthouse returns one JSON object per uploaded file/directory.
    # The last line is the root directory entry with the top-level CID.
    lines = [line.strip() for line in resp.text.strip().splitlines() if line.strip()]
    import json
    last = json.loads(lines[-1])
    cid = last["Hash"]
    return cid


# ── Cloudflare DNS update ─────────────────────────────────────────────────────

def update_cloudflare_dnslink(cid: str):
    """Update the _dnslink TXT record on Cloudflare to point to the new CID."""
    if not CLOUDFLARE_API_TOKEN or not CLOUDFLARE_ZONE_ID:
        return False

    record_name = f"_dnslink.{DNSLINK_SUBDOMAIN}"
    dnslink_value = f"dnslink=/ipfs/{cid}"

    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    base = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records"

    # Find existing TXT record
    resp = requests.get(
        base,
        headers=headers,
        params={"type": "TXT", "name": record_name},
        timeout=30,
    )
    resp.raise_for_status()
    records = resp.json().get("result", [])

    payload = {
        "type": "TXT",
        "name": record_name,
        "content": dnslink_value,
        "ttl": 60,
    }

    if records:
        # Update existing record
        record_id = records[0]["id"]
        r = requests.put(f"{base}/{record_id}", headers=headers, json=payload, timeout=30)
    else:
        # Create new record
        r = requests.post(base, headers=headers, json=payload, timeout=30)

    r.raise_for_status()
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\nDefiTracker IPFS deploy")
    print(f"  Source : {DIST_DIR}")
    print(f"  Target : Lighthouse.storage (IPFS + Filecoin)\n")

    cid = upload_to_lighthouse(DIST_DIR)

    print(f"\n✓ Deployed successfully!")
    print(f"\n  CID     : {cid}")
    print(f"  Gateway : https://gateway.lighthouse.storage/ipfs/{cid}/")
    print(f"  IPFS    : https://ipfs.io/ipfs/{cid}/")

    # Try Cloudflare auto-update
    if CLOUDFLARE_API_TOKEN and CLOUDFLARE_ZONE_ID:
        print(f"\nUpdating Cloudflare DNS ...")
        try:
            updated = update_cloudflare_dnslink(cid)
            if updated:
                print(f"  ✓ _dnslink.{DNSLINK_SUBDOMAIN} updated automatically")
                print(f"  ✓ https://{DNSLINK_SUBDOMAIN}/ will resolve to the new CID in 1-2 min")
        except Exception as e:
            print(f"  ✗ Cloudflare update failed: {e}")
            print(f"  Update DNS manually (see below)")

    # Always print manual instructions
    print(f"\n{'─' * 60}")
    print(f"DNS TXT record to update (if not auto-updated):")
    print(f"\n  Name    : _dnslink.{DNSLINK_SUBDOMAIN}")
    print(f"  Type    : TXT")
    print(f"  Value   : dnslink=/ipfs/{cid}")
    print(f"  TTL     : 60 (or lowest available)")
    print(f"{'─' * 60}\n")


if __name__ == "__main__":
    main()
