"""Database queries for user accounts and saved charts"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import bcrypt
import json

from src.database.connection import DatabaseConnection


@dataclass
class User:
    """User model"""
    user_id: int
    auth_method: str
    email: Optional[str] = None
    email_verified: bool = False
    wallet_address: Optional[str] = None
    display_name: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'user_id': self.user_id,
            'auth_method': self.auth_method,
            'email': self.email,
            'email_verified': self.email_verified,
            'wallet_address': self.wallet_address,
            'display_name': self.display_name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def get_id(self) -> str:
        """Required for Flask-Login"""
        return str(self.user_id)
    
    @property
    def is_authenticated(self) -> bool:
        """Required for Flask-Login"""
        return True
    
    @property
    def is_active(self) -> bool:
        """Required for Flask-Login"""
        return True
    
    @property
    def is_anonymous(self) -> bool:
        """Required for Flask-Login"""
        return False


@dataclass
class SavedChart:
    """Saved chart configuration model"""
    chart_id: int
    user_id: int
    name: str
    filters: Dict[str, Any]
    display_options: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'chart_id': self.chart_id,
            'user_id': self.user_id,
            'name': self.name,
            'filters': self.filters,
            'display_options': self.display_options,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class UserQueries:
    """Database queries for user operations"""
    
    def __init__(self, db: DatabaseConnection):
        self.db = db
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against its hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    # ==========================================
    # User CRUD Operations
    # ==========================================
    
    def create_email_user(
        self,
        email: str,
        password: str,
        verification_token: str,
        display_name: Optional[str] = None
    ) -> Optional[User]:
        """Create a new user with email/password authentication"""
        conn = self.db.get_connection()
        try:
            password_hash = self.hash_password(password)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (auth_method, email, password_hash, verification_token, display_name)
                    VALUES ('email', %s, %s, %s, %s)
                    RETURNING user_id, auth_method, email, email_verified, wallet_address, display_name, created_at
                """, (email, password_hash, verification_token, display_name))
                row = cur.fetchone()
                conn.commit()
                if row:
                    return User(
                        user_id=row[0],
                        auth_method=row[1],
                        email=row[2],
                        email_verified=row[3],
                        wallet_address=row[4],
                        display_name=row[5],
                        created_at=row[6]
                    )
        except Exception as e:
            conn.rollback()
            print(f"Error creating email user: {e}")
            raise
        finally:
            self.db.return_connection(conn)
        return None
    
    def create_wallet_user(
        self,
        wallet_address: str,
        display_name: Optional[str] = None
    ) -> Optional[User]:
        """Create a new user with wallet authentication"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (auth_method, wallet_address, display_name)
                    VALUES ('wallet', %s, %s)
                    RETURNING user_id, auth_method, email, email_verified, wallet_address, display_name, created_at
                """, (wallet_address, display_name))
                row = cur.fetchone()
                conn.commit()
                if row:
                    return User(
                        user_id=row[0],
                        auth_method=row[1],
                        email=row[2],
                        email_verified=row[3],
                        wallet_address=row[4],
                        display_name=row[5],
                        created_at=row[6]
                    )
        except Exception as e:
            conn.rollback()
            print(f"Error creating wallet user: {e}")
            raise
        finally:
            self.db.return_connection(conn)
        return None
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT user_id, auth_method, email, email_verified, wallet_address, display_name, created_at
                    FROM users WHERE user_id = %s
                """, (user_id,))
                row = cur.fetchone()
                if row:
                    return User(
                        user_id=row[0],
                        auth_method=row[1],
                        email=row[2],
                        email_verified=row[3],
                        wallet_address=row[4],
                        display_name=row[5],
                        created_at=row[6]
                    )
        finally:
            self.db.return_connection(conn)
        return None
    
    def get_user_by_email(self, email: str) -> Optional[tuple]:
        """Get user by email, including password hash for verification"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT user_id, auth_method, email, email_verified, wallet_address, 
                           display_name, created_at, password_hash
                    FROM users WHERE email = %s
                """, (email,))
                row = cur.fetchone()
                if row:
                    user = User(
                        user_id=row[0],
                        auth_method=row[1],
                        email=row[2],
                        email_verified=row[3],
                        wallet_address=row[4],
                        display_name=row[5],
                        created_at=row[6]
                    )
                    return (user, row[7])  # Return user and password_hash
        finally:
            self.db.return_connection(conn)
        return None
    
    def get_user_by_wallet(self, wallet_address: str) -> Optional[User]:
        """Get user by wallet address"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT user_id, auth_method, email, email_verified, wallet_address, display_name, created_at
                    FROM users WHERE wallet_address = %s
                """, (wallet_address,))
                row = cur.fetchone()
                if row:
                    return User(
                        user_id=row[0],
                        auth_method=row[1],
                        email=row[2],
                        email_verified=row[3],
                        wallet_address=row[4],
                        display_name=row[5],
                        created_at=row[6]
                    )
        finally:
            self.db.return_connection(conn)
        return None
    
    def verify_email(self, token: str) -> Optional[User]:
        """Verify user email with token"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE users 
                    SET email_verified = TRUE, verification_token = NULL
                    WHERE verification_token = %s
                    RETURNING user_id, auth_method, email, email_verified, wallet_address, display_name, created_at
                """, (token,))
                row = cur.fetchone()
                conn.commit()
                if row:
                    return User(
                        user_id=row[0],
                        auth_method=row[1],
                        email=row[2],
                        email_verified=row[3],
                        wallet_address=row[4],
                        display_name=row[5],
                        created_at=row[6]
                    )
        except Exception as e:
            conn.rollback()
            print(f"Error verifying email: {e}")
        finally:
            self.db.return_connection(conn)
        return None
    
    def set_reset_token(self, email: str, token: str) -> bool:
        """Set password reset token for user"""
        conn = self.db.get_connection()
        try:
            expires = datetime.utcnow() + timedelta(hours=1)
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE users 
                    SET reset_token = %s, reset_token_expires = %s
                    WHERE email = %s AND auth_method = 'email'
                    RETURNING user_id
                """, (token, expires, email))
                row = cur.fetchone()
                conn.commit()
                return row is not None
        except Exception as e:
            conn.rollback()
            print(f"Error setting reset token: {e}")
        finally:
            self.db.return_connection(conn)
        return False
    
    def reset_password(self, token: str, new_password: str) -> Optional[User]:
        """Reset password using token"""
        conn = self.db.get_connection()
        try:
            password_hash = self.hash_password(new_password)
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE users 
                    SET password_hash = %s, reset_token = NULL, reset_token_expires = NULL
                    WHERE reset_token = %s AND reset_token_expires > NOW()
                    RETURNING user_id, auth_method, email, email_verified, wallet_address, display_name, created_at
                """, (password_hash, token))
                row = cur.fetchone()
                conn.commit()
                if row:
                    return User(
                        user_id=row[0],
                        auth_method=row[1],
                        email=row[2],
                        email_verified=row[3],
                        wallet_address=row[4],
                        display_name=row[5],
                        created_at=row[6]
                    )
        except Exception as e:
            conn.rollback()
            print(f"Error resetting password: {e}")
        finally:
            self.db.return_connection(conn)
        return None
    
    def add_email_to_wallet_user(
        self,
        user_id: int,
        email: str,
        verification_token: str
    ) -> bool:
        """Add email to a wallet-authenticated user"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE users 
                    SET email = %s, verification_token = %s, email_verified = FALSE
                    WHERE user_id = %s AND auth_method = 'wallet' AND email IS NULL
                    RETURNING user_id
                """, (email, verification_token, user_id))
                row = cur.fetchone()
                conn.commit()
                return row is not None
        except Exception as e:
            conn.rollback()
            print(f"Error adding email to wallet user: {e}")
        finally:
            self.db.return_connection(conn)
        return False
    
    def update_display_name(self, user_id: int, display_name: str) -> bool:
        """Update user display name"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE users SET display_name = %s WHERE user_id = %s
                    RETURNING user_id
                """, (display_name, user_id))
                row = cur.fetchone()
                conn.commit()
                return row is not None
        except Exception as e:
            conn.rollback()
            print(f"Error updating display name: {e}")
        finally:
            self.db.return_connection(conn)
        return False
    
    # ==========================================
    # Wallet Challenge Operations
    # ==========================================
    
    def create_wallet_challenge(self, wallet_address: str, nonce: str) -> bool:
        """Create a new wallet authentication challenge"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                # Clean up any existing challenges for this address
                cur.execute("DELETE FROM wallet_challenges WHERE wallet_address = %s", (wallet_address,))
                # Create new challenge
                cur.execute("""
                    INSERT INTO wallet_challenges (wallet_address, nonce)
                    VALUES (%s, %s)
                """, (wallet_address, nonce))
                conn.commit()
                return True
        except Exception as e:
            conn.rollback()
            print(f"Error creating wallet challenge: {e}")
        finally:
            self.db.return_connection(conn)
        return False
    
    def get_and_delete_wallet_challenge(self, wallet_address: str) -> Optional[str]:
        """Get and delete a wallet challenge (one-time use)"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM wallet_challenges 
                    WHERE wallet_address = %s AND expires_at > NOW()
                    RETURNING nonce
                """, (wallet_address,))
                row = cur.fetchone()
                conn.commit()
                return row[0] if row else None
        except Exception as e:
            conn.rollback()
            print(f"Error getting wallet challenge: {e}")
        finally:
            self.db.return_connection(conn)
        return None
    
    def cleanup_expired_challenges(self) -> int:
        """Clean up expired wallet challenges"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM wallet_challenges WHERE expires_at < NOW()")
                count = cur.rowcount
                conn.commit()
                return count
        except Exception as e:
            conn.rollback()
            print(f"Error cleaning up challenges: {e}")
        finally:
            self.db.return_connection(conn)
        return 0


class ChartQueries:
    """Database queries for saved chart operations"""
    
    def __init__(self, db: DatabaseConnection):
        self.db = db
    
    def create_chart(
        self,
        user_id: int,
        name: str,
        filters: Dict[str, Any],
        display_options: Optional[Dict[str, Any]] = None
    ) -> Optional[SavedChart]:
        """Create a new saved chart"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO saved_charts (user_id, name, filters, display_options)
                    VALUES (%s, %s, %s, %s)
                    RETURNING chart_id, user_id, name, filters, display_options, created_at, updated_at
                """, (user_id, name, json.dumps(filters), json.dumps(display_options) if display_options else None))
                row = cur.fetchone()
                conn.commit()
                if row:
                    return SavedChart(
                        chart_id=row[0],
                        user_id=row[1],
                        name=row[2],
                        filters=row[3],
                        display_options=row[4],
                        created_at=row[5],
                        updated_at=row[6]
                    )
        except Exception as e:
            conn.rollback()
            print(f"Error creating chart: {e}")
        finally:
            self.db.return_connection(conn)
        return None
    
    def get_chart_by_id(self, chart_id: int) -> Optional[SavedChart]:
        """Get a chart by ID"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT chart_id, user_id, name, filters, display_options, created_at, updated_at
                    FROM saved_charts WHERE chart_id = %s
                """, (chart_id,))
                row = cur.fetchone()
                if row:
                    return SavedChart(
                        chart_id=row[0],
                        user_id=row[1],
                        name=row[2],
                        filters=row[3],
                        display_options=row[4],
                        created_at=row[5],
                        updated_at=row[6]
                    )
        finally:
            self.db.return_connection(conn)
        return None
    
    def get_user_charts(self, user_id: int) -> List[SavedChart]:
        """Get all charts for a user"""
        conn = self.db.get_connection()
        charts = []
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT chart_id, user_id, name, filters, display_options, created_at, updated_at
                    FROM saved_charts 
                    WHERE user_id = %s
                    ORDER BY updated_at DESC
                """, (user_id,))
                for row in cur.fetchall():
                    charts.append(SavedChart(
                        chart_id=row[0],
                        user_id=row[1],
                        name=row[2],
                        filters=row[3],
                        display_options=row[4],
                        created_at=row[5],
                        updated_at=row[6]
                    ))
        finally:
            self.db.return_connection(conn)
        return charts
    
    def update_chart(
        self,
        chart_id: int,
        user_id: int,
        name: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        display_options: Optional[Dict[str, Any]] = None
    ) -> Optional[SavedChart]:
        """Update a saved chart (only if owned by user)"""
        conn = self.db.get_connection()
        try:
            # Build dynamic update query
            updates = []
            params = []
            if name is not None:
                updates.append("name = %s")
                params.append(name)
            if filters is not None:
                updates.append("filters = %s")
                params.append(json.dumps(filters))
            if display_options is not None:
                updates.append("display_options = %s")
                params.append(json.dumps(display_options))
            
            if not updates:
                return self.get_chart_by_id(chart_id)
            
            params.extend([chart_id, user_id])
            
            with conn.cursor() as cur:
                cur.execute(f"""
                    UPDATE saved_charts 
                    SET {', '.join(updates)}
                    WHERE chart_id = %s AND user_id = %s
                    RETURNING chart_id, user_id, name, filters, display_options, created_at, updated_at
                """, params)
                row = cur.fetchone()
                conn.commit()
                if row:
                    return SavedChart(
                        chart_id=row[0],
                        user_id=row[1],
                        name=row[2],
                        filters=row[3],
                        display_options=row[4],
                        created_at=row[5],
                        updated_at=row[6]
                    )
        except Exception as e:
            conn.rollback()
            print(f"Error updating chart: {e}")
        finally:
            self.db.return_connection(conn)
        return None
    
    def delete_chart(self, chart_id: int, user_id: int) -> bool:
        """Delete a saved chart (only if owned by user)"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM saved_charts 
                    WHERE chart_id = %s AND user_id = %s
                    RETURNING chart_id
                """, (chart_id, user_id))
                row = cur.fetchone()
                conn.commit()
                return row is not None
        except Exception as e:
            conn.rollback()
            print(f"Error deleting chart: {e}")
        finally:
            self.db.return_connection(conn)
        return False

