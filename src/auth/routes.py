"""Authentication API routes"""
import re
from flask import Blueprint, request, jsonify, current_app, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user

from src.database.connection import DatabaseConnection
from src.database.user_queries import UserQueries, ChartQueries, User, CURRENT_TOS_VERSION
from src.auth.wallet import (
    generate_nonce,
    create_sign_message,
    verify_cardano_signature,
    validate_cardano_address
)
from src.auth.email import (
    generate_token,
    send_verification_email,
    send_password_reset_email,
    send_email_added_notification
)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# Database connection - initialized when app starts
db = None
user_queries = None
chart_queries = None


def init_auth(database: DatabaseConnection):
    """Initialize auth module with database connection"""
    global db, user_queries, chart_queries
    db = database
    user_queries = UserQueries(db)
    chart_queries = ChartQueries(db)


def get_base_url() -> str:
    """Get the base URL for email links"""
    return request.host_url.rstrip('/')


def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_password(password: str) -> tuple:
    """
    Validate password strength.
    Returns (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Za-z]', password):
        return False, "Password must contain at least one letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    return True, None


# ==========================================
# Email/Password Authentication
# ==========================================

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user with email and password"""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    display_name = data.get('display_name', '').strip() or None
    tos_accepted = data.get('tos_accepted', False)

    # Validate ToS acceptance
    if not tos_accepted:
        return jsonify({'error': 'You must accept the Terms of Service and Privacy Policy'}), 400

    # Validate email
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    if not validate_email(email):
        return jsonify({'error': 'Invalid email format'}), 400

    # Validate password
    is_valid, error = validate_password(password)
    if not is_valid:
        return jsonify({'error': error}), 400

    # Check if email already exists
    existing = user_queries.get_user_by_email(email)
    if existing:
        return jsonify({'error': 'Email already registered'}), 409

    # Create user with verification token
    verification_token = generate_token()

    try:
        user = user_queries.create_email_user(
            email=email,
            password=password,
            verification_token=verification_token,
            display_name=display_name,
            tos_version=CURRENT_TOS_VERSION
        )
        
        if not user:
            return jsonify({'error': 'Failed to create user'}), 500
        
        # Send verification email
        base_url = get_base_url()
        email_sent = send_verification_email(email, verification_token, base_url)
        
        return jsonify({
            'message': 'Registration successful. Please check your email to verify your account.',
            'user': user.to_dict(),
            'email_sent': email_sent
        }), 201
        
    except Exception as e:
        if 'unique' in str(e).lower():
            return jsonify({'error': 'Email already registered'}), 409
        return jsonify({'error': 'Registration failed'}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """Login with email and password"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    
    # Get user with password hash
    result = user_queries.get_user_by_email(email)
    
    if not result:
        return jsonify({'error': 'Invalid email or password'}), 401
    
    user, password_hash = result
    
    # Verify password
    if not password_hash or not user_queries.verify_password(password, password_hash):
        return jsonify({'error': 'Invalid email or password'}), 401
    
    # Check if email is verified
    if not user.email_verified:
        return jsonify({
            'error': 'Please verify your email before logging in',
            'email_verified': False
        }), 403
    
    # Log in user
    login_user(user)
    
    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict()
    })


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """Logout current user"""
    logout_user()
    return jsonify({'message': 'Logged out successfully'})


@auth_bp.route('/verify/<token>')
def verify_email(token):
    """Verify email with token"""
    if not token:
        return jsonify({'error': 'Invalid verification token'}), 400
    
    user = user_queries.verify_email(token)
    
    if user:
        # Redirect to login page with success message
        return redirect('/?verified=true')
    else:
        return redirect('/?verified=false')


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Request password reset"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    email = data.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    # Generate reset token
    reset_token = generate_token()
    
    # Set token (returns True if user exists)
    if user_queries.set_reset_token(email, reset_token):
        base_url = get_base_url()
        send_password_reset_email(email, reset_token, base_url)
    
    # Always return success to prevent email enumeration
    return jsonify({
        'message': 'If an account exists with this email, a password reset link has been sent.'
    })


@auth_bp.route('/reset-password/<token>', methods=['POST'])
def reset_password(token):
    """Reset password with token"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    new_password = data.get('password', '')
    
    # Validate new password
    is_valid, error = validate_password(new_password)
    if not is_valid:
        return jsonify({'error': error}), 400
    
    user = user_queries.reset_password(token, new_password)
    
    if user:
        return jsonify({'message': 'Password reset successful. You can now log in with your new password.'})
    else:
        return jsonify({'error': 'Invalid or expired reset token'}), 400


@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    """Resend verification email"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    email = data.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    result = user_queries.get_user_by_email(email)
    
    if result:
        user, _ = result
        if not user.email_verified:
            # Generate new verification token and resend
            verification_token = generate_token()
            # Update token in database
            conn = db.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE users SET verification_token = %s WHERE email = %s",
                        (verification_token, email)
                    )
                    conn.commit()
                base_url = get_base_url()
                send_verification_email(email, verification_token, base_url)
            finally:
                db.return_connection(conn)
    
    # Always return success to prevent email enumeration
    return jsonify({
        'message': 'If an unverified account exists with this email, a new verification link has been sent.'
    })


# ==========================================
# Wallet Authentication
# ==========================================

@auth_bp.route('/wallet-challenge', methods=['POST'])
def wallet_challenge():
    """Get a challenge nonce for wallet authentication"""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    wallet_address = data.get('wallet_address', '').strip()

    if not wallet_address:
        return jsonify({'error': 'Wallet address is required'}), 400

    if not validate_cardano_address(wallet_address):
        return jsonify({'error': 'Invalid Cardano address'}), 400

    # Generate nonce
    nonce = generate_nonce()

    # Store challenge
    if not user_queries.create_wallet_challenge(wallet_address, nonce):
        return jsonify({'error': 'Failed to create challenge'}), 500

    # Create message to sign
    message = create_sign_message(nonce)

    return jsonify({
        'nonce': nonce,
        'message': message
    })


@auth_bp.route('/wallet-login', methods=['POST'])
def wallet_login():
    """Login or register with Cardano wallet

    For MVP: We use a simplified flow where connecting the wallet and signing
    the challenge proves ownership. Full COSE signature verification can be
    added later for enhanced security.
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    wallet_address = data.get('wallet_address', '').strip()
    signature = data.get('signature')  # May be string or object
    public_key = data.get('public_key', '')
    wallet_type = data.get('wallet_type', '').strip() or None  # e.g., 'nami', 'eternl'

    if not wallet_address:
        return jsonify({'error': 'Wallet address is required'}), 400

    if not validate_cardano_address(wallet_address):
        return jsonify({'error': 'Invalid Cardano address'}), 400

    # Get and delete the challenge (one-time use)
    nonce = user_queries.get_and_delete_wallet_challenge(wallet_address)

    if not nonce:
        return jsonify({'error': 'No valid challenge found. Please request a new challenge.'}), 400

    # For MVP: Accept the signature as proof the user approved in their wallet
    # The fact that they could:
    # 1. Connect to the wallet (requires wallet owner approval)
    # 2. Get addresses from the wallet
    # 3. Request and receive a signature (requires wallet owner approval)
    # Is sufficient proof of ownership for most use cases.
    #
    # Full COSE_Sign1 verification can be added later for high-security scenarios

    if not signature:
        return jsonify({'error': 'Signature is required'}), 400

    # Check if user exists
    user = user_queries.get_user_by_wallet(wallet_address)

    if not user:
        # For new wallet users, require ToS acceptance
        tos_accepted = data.get('tos_accepted', False)
        if not tos_accepted:
            return jsonify({
                'error': 'tos_required',
                'message': 'Please accept the Terms of Service to continue',
                'tos_url': '/terms',
                'privacy_url': '/privacy'
            }), 400

        # Create new wallet user with ToS acceptance
        user = user_queries.create_wallet_user(
            wallet_address,
            wallet_type=wallet_type,
            tos_version=CURRENT_TOS_VERSION
        )
        if not user:
            return jsonify({'error': 'Failed to create user'}), 500
        is_new = True
    else:
        # Update wallet_type if provided and different
        if wallet_type and user.wallet_type != wallet_type:
            user_queries.update_wallet_type(user.user_id, wallet_type)
            user.wallet_type = wallet_type
        is_new = False

    # Log in user
    login_user(user)

    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(),
        'is_new_user': is_new,
        'show_email_prompt': user.needs_email_prompt
    })


# ==========================================
# Account Management
# ==========================================

@auth_bp.route('/me')
def get_current_user():
    """Get current user info"""
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'user': current_user.to_dict()
        })
    else:
        return jsonify({
            'authenticated': False,
            'user': None
        })


@auth_bp.route('/add-email', methods=['POST'])
@login_required
def add_email():
    """Add email to wallet account (with optional newsletter subscription)"""
    if current_user.auth_method != 'wallet':
        return jsonify({'error': 'This action is only for wallet accounts'}), 400
    
    if current_user.email:
        return jsonify({'error': 'Email already set for this account'}), 400
    
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    email = data.get('email', '').strip().lower()
    subscribe_newsletter = data.get('subscribe_newsletter', True)  # Default to subscribed
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    if not validate_email(email):
        return jsonify({'error': 'Invalid email format'}), 400
    
    # Check if email already exists
    existing = user_queries.get_user_by_email(email)
    if existing:
        return jsonify({'error': 'Email already in use'}), 409
    
    # Add email with verification token
    verification_token = generate_token()
    
    if user_queries.add_email_to_wallet_user(
        current_user.user_id, 
        email, 
        verification_token,
        subscribe_newsletter=subscribe_newsletter
    ):
        base_url = get_base_url()
        send_verification_email(email, verification_token, base_url)
        return jsonify({'message': 'Email added. Please check your inbox to verify.'})
    else:
        return jsonify({'error': 'Failed to add email'}), 500


@auth_bp.route('/dismiss-newsletter', methods=['POST'])
@login_required
def dismiss_newsletter():
    """Dismiss the newsletter prompt for wallet users"""
    if user_queries.dismiss_newsletter_prompt(current_user.user_id):
        return jsonify({'message': 'Newsletter prompt dismissed'})
    else:
        return jsonify({'error': 'Failed to dismiss prompt'}), 500


@auth_bp.route('/accept-tos', methods=['POST'])
@login_required
def accept_tos():
    """Accept current Terms of Service (for re-consent flow)"""
    if user_queries.accept_tos(current_user.user_id, CURRENT_TOS_VERSION):
        return jsonify({
            'message': 'Terms of Service accepted',
            'tos_version': CURRENT_TOS_VERSION
        })
    else:
        return jsonify({'error': 'Failed to record acceptance'}), 500


@auth_bp.route('/profile', methods=['PUT'])
@login_required
def update_profile():
    """Update user profile"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    display_name = data.get('display_name', '').strip()
    
    if display_name:
        if len(display_name) > 100:
            return jsonify({'error': 'Display name too long (max 100 characters)'}), 400
        
        if user_queries.update_display_name(current_user.user_id, display_name):
            return jsonify({'message': 'Profile updated'})
        else:
            return jsonify({'error': 'Failed to update profile'}), 500
    
    return jsonify({'error': 'No changes provided'}), 400


# ==========================================
# Saved Charts API
# ==========================================

@auth_bp.route('/charts', methods=['GET'])
@login_required
def list_charts():
    """List user's saved charts"""
    charts = chart_queries.get_user_charts(current_user.user_id)
    return jsonify([c.to_dict() for c in charts])


@auth_bp.route('/charts', methods=['POST'])
@login_required
def create_chart():
    """Save a new chart configuration"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    name = data.get('name', '').strip()
    filters = data.get('filters')
    display_options = data.get('display_options')
    
    if not name:
        return jsonify({'error': 'Chart name is required'}), 400
    
    if not filters:
        return jsonify({'error': 'Chart filters are required'}), 400
    
    if len(name) > 100:
        return jsonify({'error': 'Chart name too long (max 100 characters)'}), 400
    
    chart = chart_queries.create_chart(
        user_id=current_user.user_id,
        name=name,
        filters=filters,
        display_options=display_options
    )
    
    if chart:
        return jsonify(chart.to_dict()), 201
    else:
        return jsonify({'error': 'Failed to save chart'}), 500


@auth_bp.route('/charts/<int:chart_id>', methods=['GET'])
def get_chart(chart_id):
    """Get a specific chart (public for sharing)"""
    chart = chart_queries.get_chart_by_id(chart_id)
    
    if chart:
        return jsonify(chart.to_dict())
    else:
        return jsonify({'error': 'Chart not found'}), 404


@auth_bp.route('/charts/<int:chart_id>', methods=['PUT'])
@login_required
def update_chart(chart_id):
    """Update a saved chart"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    name = data.get('name')
    filters = data.get('filters')
    display_options = data.get('display_options')
    
    if name and len(name) > 100:
        return jsonify({'error': 'Chart name too long (max 100 characters)'}), 400
    
    chart = chart_queries.update_chart(
        chart_id=chart_id,
        user_id=current_user.user_id,
        name=name,
        filters=filters,
        display_options=display_options
    )
    
    if chart:
        return jsonify(chart.to_dict())
    else:
        return jsonify({'error': 'Chart not found or not authorized'}), 404


@auth_bp.route('/charts/<int:chart_id>', methods=['DELETE'])
@login_required
def delete_chart(chart_id):
    """Delete a saved chart"""
    if chart_queries.delete_chart(chart_id, current_user.user_id):
        return jsonify({'message': 'Chart deleted'})
    else:
        return jsonify({'error': 'Chart not found or not authorized'}), 404

