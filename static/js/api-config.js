/**
 * API base URL configuration for IPFS-hosted frontend.
 *
 * When served from IPFS, window.API_BASE_URL is injected by export_static.py
 * as an inline <script> before this file loads.
 *
 * When served directly from Flask (local dev), this file is not loaded
 * at all — Flask serves its own routes at relative /api/ paths.
 *
 * Fallback to empty string so fetch calls work same-origin in local dev
 * if this file happens to be loaded.
 */
window.API_BASE_URL = window.API_BASE_URL || '';

/**
 * Drop-in replacement for fetch() that prepends API_BASE_URL to /api/ paths.
 * Always includes credentials so session cookies are sent cross-origin.
 */
window.apiFetch = function(path, options) {
    var opts = options || {};
    opts.credentials = opts.credentials || 'include';
    return fetch(window.API_BASE_URL + path, opts);
};

/**
 * Cached Promise resolving to the current user object, or null if not logged in.
 * Settled once per page load — all pages use this to drive conditional UI
 * instead of relying on server-side current_user Jinja rendering.
 */
window._authState = window.apiFetch('/api/auth/me')
    .then(function(r) { return r.ok ? r.json() : null; })
    .catch(function() { return null; });
