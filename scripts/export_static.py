#!/usr/bin/env python3
"""
Render Jinja2 templates to static HTML for IPFS deployment.

Produces a dist/ directory with pre-rendered HTML, rewritten API fetch calls,
and a full copy of static assets. No Flask runtime required.

Usage (from project root):
    python scripts/export_static.py

Environment variables:
    API_BASE_URL  URL of the Flask backend API server (default: https://api.yieldlife.io)
"""

import os
import re
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

# ── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"
DIST_DIR = PROJECT_ROOT / "dist"

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.yieldlife.xyz")

# ── Fake anonymous user ───────────────────────────────────────────────────────
# Replaces Flask-Login's current_user in all Jinja2 templates.
# is_authenticated=False renders the "Login" button state for all pages.
# wallet_address is a non-empty placeholder so that any [:N] slice in
# templates (e.g. portfolio.html) doesn't raise a TypeError.

class AnonymousUser:
    is_authenticated = False
    is_active = False
    is_anonymous = True
    wallet_address = "addr1qxxxxxxxxxxxx"
    wallet_type = None
    email = None
    needs_tos_acceptance = False

    def get_id(self):
        return None


# ── Jinja2 environment ────────────────────────────────────────────────────────

env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)

# Inject current_user globally — mirrors Flask's context_processor in app.py
env.globals["current_user"] = AnonymousUser()


# ── Pages to render ───────────────────────────────────────────────────────────
# (template_name, output_path_relative_to_dist, extra_context)

PAGES = [
    ("index.html",           "index.html",                    {}),
    ("cardano_lps.html",     "cardano/lps/index.html",        {"chain": "cardano", "yield_type": "lp"}),
    ("cardano_lending.html", "cardano/lending/index.html",    {"chain": "cardano", "yield_type": "supply"}),
    ("my_charts.html",       "my-charts/index.html",          {}),
    ("portfolio.html",       "portfolio/index.html",          {}),
    ("myportfolio.html",     "myportfolio/index.html",        {}),
    ("terms.html",           "terms/index.html",              {}),
    ("privacy.html",         "privacy/index.html",            {}),
]


# ── Post-processing helpers ───────────────────────────────────────────────────

API_CONFIG_INJECTION = (
    f'<script>window.API_BASE_URL = "{API_BASE_URL}";</script>\n'
    '    <script src="/static/js/api-config.js"></script>'
)

PORTFOLIO_AUTH_GUARD = """\
    // IPFS static: redirect unauthenticated users to home
    window._authState.then(function(user) {
        if (!user) { window.location.href = '/'; }
    });
"""


def inject_api_config(html: str) -> str:
    """Insert API_BASE_URL + api-config.js as the very first scripts in <head>."""
    # Insert just before the first <script or <link in <head>
    # Fallback: insert before </head>
    match = re.search(r'(<script\b|<link\b)', html, re.IGNORECASE)
    if match:
        pos = match.start()
        return html[:pos] + API_CONFIG_INJECTION + "\n    " + html[pos:]
    return html.replace("</head>", API_CONFIG_INJECTION + "\n</head>", 1)


def rewrite_fetch_calls(content: str) -> str:
    """Replace fetch('/api/... with window.apiFetch('/api/... in JS content."""
    # Handle both single-quote, double-quote, and template-literal variants
    content = content.replace("fetch('/api/", "window.apiFetch('/api/")
    content = content.replace('fetch("/api/', 'window.apiFetch("/api/')
    content = content.replace("fetch(`/api/", "window.apiFetch(`/api/")
    return content


def inject_portfolio_auth_guard(js_content: str) -> str:
    """Prepend an auth guard inside the DOMContentLoaded listener."""
    # Find the DOMContentLoaded callback body start
    pattern = r"(document\.addEventListener\('DOMContentLoaded',\s*function\s*\(\)\s*\{)"
    match = re.search(pattern, js_content)
    if match:
        insert_at = match.end()
        return js_content[:insert_at] + "\n" + PORTFOLIO_AUTH_GUARD + js_content[insert_at:]
    return js_content


def rewrite_embed_html(html: str) -> str:
    """
    Replace the Jinja-rendered static config block in embed.html with
    runtime URL-param reading. Also fixes the hardcoded localhost URL.

    The export renders embed.html with default values, producing something like:
        const chain = "cardano";
        const protocol = "minswap";
        const asset = "";
        const days = 30;
        const url = `http://localhost:5000/api/...`;

    We replace the entire block from `const chain` through the fetch call
    with param-driven JS.
    """
    replacement = (
        'const params = new URLSearchParams(window.location.search);\n'
        '        const chain = params.get(\'chain\') || \'cardano\';\n'
        '        const protocol = params.get(\'protocol\') || \'minswap\';\n'
        '        const asset = params.get(\'asset\') || \'\';\n'
        '        const days = parseInt(params.get(\'days\') || \'30\');\n'
        '\n'
        '        const url = `${window.API_BASE_URL}/api/${chain}/${protocol}/history'
        '?days=${days}${asset ? \'&asset=\' + asset : \'\'}`;\n'
        '        const response = await fetch(url);\n'
    )

    # Replace: from "const chain = ..." through "const response = await fetch(url);"
    pattern = (
        r"const chain\s*=\s*[\"'].*?[\"'];.*?"
        r"const response\s*=\s*await fetch\(url\);"
    )
    rewritten = re.sub(pattern, replacement, html, flags=re.DOTALL)

    # Fix title div: replace Jinja-rendered static title with JS-driven one
    title_pattern = r'<div id="title">[^<]*</div>'
    title_replacement = '<div id="title"></div>'
    rewritten = re.sub(title_pattern, title_replacement, rewritten)

    # Add JS title setter right after the url/response block
    title_js = (
        '\n        document.getElementById(\'title\').textContent =\n'
        '            `${protocol.charAt(0).toUpperCase() + protocol.slice(1)}'
        ' - ${asset || \'All Assets\'}`;\n'
    )
    rewritten = rewritten.replace(
        "const response = await fetch(url);\n",
        "const response = await fetch(url);\n" + title_js,
        1
    )

    return rewritten


def fix_localhost_urls(html: str) -> str:
    """Replace any remaining hardcoded localhost:5000 references."""
    return html.replace("http://localhost:5000", API_BASE_URL)


# ── Main export logic ─────────────────────────────────────────────────────────

def render_pages():
    """Render all Jinja2 pages to dist/."""
    print(f"Rendering templates → {DIST_DIR}/")

    for template_name, output_path, context in PAGES:
        tmpl = env.get_template(template_name)
        html = tmpl.render(**context)

        # Apply post-processing passes
        html = inject_api_config(html)
        html = rewrite_fetch_calls(html)
        html = fix_localhost_urls(html)

        out = DIST_DIR / output_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(f"  ✓ {template_name} → dist/{output_path}")

    # embed.html — special handling
    tmpl = env.get_template("embed.html")
    html = tmpl.render(chain="cardano", protocol="minswap", asset="", days=30)
    html = inject_api_config(html)
    html = rewrite_embed_html(html)
    html = fix_localhost_urls(html)
    out = DIST_DIR / "embed" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"  ✓ embed.html → dist/embed/index.html")


def copy_and_patch_static():
    """Copy static/ into dist/static/ and patch JS files."""
    dist_static = DIST_DIR / "static"
    if dist_static.exists():
        shutil.rmtree(dist_static)
    shutil.copytree(STATIC_DIR, dist_static)
    print(f"  ✓ Copied static/ → dist/static/")

    # Patch JS files: rewrite fetch('/api/...) calls
    for js_file in (dist_static / "js").glob("*.js"):
        content = js_file.read_text(encoding="utf-8")
        patched = rewrite_fetch_calls(content)

        # Inject auth guard into portfolio JS copies
        if js_file.name in ("portfolio.js", "myportfolio.js"):
            patched = inject_portfolio_auth_guard(patched)
            print(f"  ✓ Patched {js_file.name} (fetch rewrite + auth guard)")
        elif patched != content:
            print(f"  ✓ Patched {js_file.name} (fetch rewrite)")

        js_file.write_text(patched, encoding="utf-8")


def main():
    print(f"\nDefiTracker static export")
    print(f"  API_BASE_URL : {API_BASE_URL}")
    print(f"  Output       : {DIST_DIR}\n")

    # Clean output directory
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir()

    render_pages()
    print()
    copy_and_patch_static()

    print(f"\nDone. dist/ is ready for IPFS deployment.\n")


if __name__ == "__main__":
    main()
