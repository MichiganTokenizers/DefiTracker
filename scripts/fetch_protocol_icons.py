#!/usr/bin/env python3
"""
Fetch protocol favicons/icons and save them to static folder.
Uses multiple methods to get the best quality icon available.
"""

import os
import sys
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static')

# Protocol websites - maps protocol name to website URL
PROTOCOLS = {
    # Cardano protocols
    'minswap': 'https://minswap.org',
    'sundaeswap': 'https://sundaeswap.finance',
    'wingriders': 'https://wingriders.com',
    'liqwid': 'https://liqwid.finance',
    'muesliswap': 'https://muesliswap.com',
    # Flare protocols
    'kinetic': 'https://kinetic.market',
    'blazeswap': 'https://blazeswap.xyz',
}

# Cardano wallet websites - maps wallet id to website URL
WALLETS = {
    'nami': 'https://namiwallet.io',
    'eternl': 'https://eternl.io',
    'flint': 'https://flint-wallet.com',
    'lace': 'https://www.lace.io',
    'yoroi': 'https://yoroi-wallet.com',
    'begin': 'https://begin.is',
    'gerowallet': 'https://gerowallet.io',
    'typhon': 'https://typhonwallet.io',
    'nufi': 'https://nu.fi',
}

# Request headers to appear as a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
}


def get_extension_from_url(url):
    """Extract file extension from URL."""
    path = urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    if ext in ['.png', '.jpg', '.jpeg', '.ico', '.svg', '.webp', '.gif']:
        return ext
    return '.png'  # Default to png


def get_extension_from_content_type(content_type):
    """Get file extension from content-type header."""
    if not content_type:
        return '.png'
    content_type = content_type.lower()
    if 'svg' in content_type:
        return '.svg'
    elif 'png' in content_type:
        return '.png'
    elif 'jpeg' in content_type or 'jpg' in content_type:
        return '.jpg'
    elif 'webp' in content_type:
        return '.webp'
    elif 'gif' in content_type:
        return '.gif'
    elif 'icon' in content_type or 'ico' in content_type:
        return '.ico'
    return '.png'


def find_best_icon_from_html(url):
    """
    Parse HTML to find the best quality icon.
    Prioritizes: apple-touch-icon > large icons > regular favicon
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        icons = []
        
        # Look for all icon link tags
        for link in soup.find_all('link', rel=True):
            rel = link.get('rel', [])
            if isinstance(rel, str):
                rel = [rel]
            rel_str = ' '.join(rel).lower()
            
            href = link.get('href')
            if not href:
                continue
            
            # Score icons by quality
            score = 0
            size = 0
            
            if 'apple-touch-icon' in rel_str:
                score = 100  # Highest priority - usually 180x180 or larger
            elif 'icon' in rel_str:
                score = 50
            elif 'shortcut' in rel_str:
                score = 40
            else:
                continue
            
            # Check for size attribute
            sizes = link.get('sizes', '')
            if sizes and 'x' in sizes:
                try:
                    size = int(sizes.split('x')[0])
                    score += size  # Bigger is better
                except ValueError:
                    pass
            
            icon_url = urljoin(url, href)
            icons.append((score, size, icon_url))
        
        # Sort by score (highest first)
        icons.sort(reverse=True)
        
        if icons:
            return icons[0][2]  # Return URL of best icon
        
        return None
        
    except Exception as e:
        print(f"  Error parsing HTML: {e}")
        return None


def try_download_icon(icon_url, save_path):
    """Try to download an icon from URL."""
    try:
        response = requests.get(icon_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        # Check if we actually got an image
        content_type = response.headers.get('content-type', '')
        if 'text/html' in content_type.lower():
            print(f"  Got HTML instead of image from {icon_url}")
            return False
        
        # Get proper extension
        ext = get_extension_from_content_type(content_type)
        if not ext:
            ext = get_extension_from_url(icon_url)
        
        # Update save path with correct extension
        base_path = os.path.splitext(save_path)[0]
        save_path = base_path + ext
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        
        print(f"  Saved: {save_path} ({len(response.content)} bytes)")
        return save_path
        
    except Exception as e:
        print(f"  Failed to download {icon_url}: {e}")
        return False


def fetch_icon_google(domain, save_path):
    """Fetch icon using Google's favicon service (fallback)."""
    url = f"https://www.google.com/s2/favicons?sz=128&domain={domain}"
    return try_download_icon(url, save_path)


def fetch_icon_duckduckgo(domain, save_path):
    """Fetch icon using DuckDuckGo's service (fallback)."""
    url = f"https://icons.duckduckgo.com/ip3/{domain}.ico"
    return try_download_icon(url, save_path)


def fetch_icon(name, website_url, prefix=''):
    """
    Fetch icon for a protocol or wallet using multiple methods.
    Returns the path to the saved icon or None.

    Args:
        name: Protocol or wallet name
        website_url: Website URL to fetch icon from
        prefix: Optional prefix for filename (e.g., 'wallet-' for wallet icons)
    """
    print(f"\n{'='*50}")
    print(f"Fetching icon for: {name}")
    print(f"Website: {website_url}")
    print('='*50)

    domain = urlparse(website_url).netloc
    filename = f"{prefix}{name}-logo" if prefix else f"{name}-logo"
    base_save_path = os.path.join(STATIC_DIR, filename)
    
    # Method 1: Parse HTML for best icon (apple-touch-icon, etc.)
    print("\n  Method 1: Parsing HTML for high-quality icons...")
    icon_url = find_best_icon_from_html(website_url)
    if icon_url:
        print(f"  Found icon: {icon_url}")
        result = try_download_icon(icon_url, base_save_path)
        if result:
            return result
    
    # Method 2: Try common favicon paths
    print("\n  Method 2: Trying common favicon paths...")
    common_paths = [
        '/apple-touch-icon.png',
        '/apple-touch-icon-180x180.png',
        '/apple-touch-icon-152x152.png',
        '/favicon-192x192.png',
        '/favicon-96x96.png',
        '/favicon.png',
        '/favicon.ico',
        '/icon.png',
    ]
    
    for path in common_paths:
        icon_url = urljoin(website_url, path)
        print(f"  Trying: {path}")
        result = try_download_icon(icon_url, base_save_path)
        if result:
            return result
    
    # Method 3: Google's favicon service
    print("\n  Method 3: Trying Google favicon service...")
    result = fetch_icon_google(domain, base_save_path)
    if result:
        return result
    
    # Method 4: DuckDuckGo's icon service
    print("\n  Method 4: Trying DuckDuckGo icon service...")
    result = fetch_icon_duckduckgo(domain, base_save_path)
    if result:
        return result
    
    print(f"\n  ❌ Could not fetch icon for {name}")
    return None


def fetch_protocol_icon(protocol_name, website_url):
    """Fetch icon for a protocol (wrapper for backwards compatibility)."""
    return fetch_icon(protocol_name, website_url)


def fetch_wallet_icon(wallet_name, website_url):
    """Fetch icon for a wallet."""
    return fetch_icon(wallet_name, website_url, prefix='wallet-')


def main():
    """Fetch icons for all protocols and wallets."""
    import argparse

    parser = argparse.ArgumentParser(description='Fetch protocol and wallet icons')
    parser.add_argument('--protocols', action='store_true', help='Fetch protocol icons only')
    parser.add_argument('--wallets', action='store_true', help='Fetch wallet icons only')
    args = parser.parse_args()

    # If neither flag is set, fetch both
    fetch_protocols = args.protocols or (not args.protocols and not args.wallets)
    fetch_wallets = args.wallets or (not args.protocols and not args.wallets)

    print("="*60)
    print("DeFi Protocol & Wallet Icon Fetcher")
    print("="*60)
    print(f"\nStatic directory: {STATIC_DIR}")

    if not os.path.exists(STATIC_DIR):
        print(f"Creating static directory: {STATIC_DIR}")
        os.makedirs(STATIC_DIR)

    protocol_results = {}
    wallet_results = {}

    # Fetch protocol icons
    if fetch_protocols:
        print("\n" + "="*60)
        print("FETCHING PROTOCOL ICONS")
        print("="*60)
        for protocol, url in PROTOCOLS.items():
            result = fetch_protocol_icon(protocol, url)
            protocol_results[protocol] = result

    # Fetch wallet icons
    if fetch_wallets:
        print("\n" + "="*60)
        print("FETCHING WALLET ICONS")
        print("="*60)
        for wallet, url in WALLETS.items():
            result = fetch_wallet_icon(wallet, url)
            wallet_results[wallet] = result

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    total_success = 0
    total_count = 0

    if fetch_protocols and protocol_results:
        print("\nProtocols:")
        success_count = 0
        for protocol, path in protocol_results.items():
            if path:
                print(f"  ✅ {protocol}: {os.path.basename(path)}")
                success_count += 1
            else:
                print(f"  ❌ {protocol}: FAILED")
        print(f"  Fetched {success_count}/{len(PROTOCOLS)} protocol icons")
        total_success += success_count
        total_count += len(PROTOCOLS)

    if fetch_wallets and wallet_results:
        print("\nWallets:")
        success_count = 0
        for wallet, path in wallet_results.items():
            if path:
                print(f"  ✅ {wallet}: {os.path.basename(path)}")
                success_count += 1
            else:
                print(f"  ❌ {wallet}: FAILED")
        print(f"  Fetched {success_count}/{len(WALLETS)} wallet icons")
        total_success += success_count
        total_count += len(WALLETS)

    # Print JS mapping for chain.html
    if fetch_protocols and protocol_results:
        print("\n" + "="*60)
        print("JavaScript protocolLogos mapping for chain.html:")
        print("="*60)
        print("const protocolLogos = {")
        for protocol, path in protocol_results.items():
            if path:
                filename = os.path.basename(path)
                print(f"    '{protocol}': '/static/{filename}',")
        print("};")

    # Print JS mapping for wallet-connect.js
    if fetch_wallets and wallet_results:
        print("\n" + "="*60)
        print("JavaScript SUPPORTED_WALLETS icons for wallet-connect.js:")
        print("="*60)
        print("const SUPPORTED_WALLETS = [")
        wallet_ids = {
            'nami': 'nami',
            'eternl': 'eternl',
            'flint': 'flint',
            'lace': 'lace',
            'yoroi': 'yoroi',
            'begin': 'begin',
            'gerowallet': 'gerowallet',
            'typhon': 'typhoncip30',
            'nufi': 'nufi',
        }
        for wallet, path in wallet_results.items():
            if path:
                filename = os.path.basename(path)
                wallet_id = wallet_ids.get(wallet, wallet)
                wallet_name = wallet.capitalize()
                if wallet == 'gerowallet':
                    wallet_name = 'GeroWallet'
                elif wallet == 'nufi':
                    wallet_name = 'NuFi'
                print(f"    {{ id: '{wallet_id}', name: '{wallet_name}', icon: '/static/{filename}' }},")
        print("];")

    return 0 if total_success == total_count else 1


if __name__ == '__main__':
    sys.exit(main())

