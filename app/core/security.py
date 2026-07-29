from datetime import datetime, timedelta, timezone
import bcrypt
import jwt

# Secret key used to cryptographically sign JWT tokens (keep this secret in production!)
SECRET_KEY = "super_secret_community_app_key_change_in_production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # Token valid for 24 hours


def hash_password(password: str) -> str:
    """Converts a plain-text password into a secure bcrypt hash string."""
    # Convert string to bytes
    password_bytes = password.encode("utf-8")
    # Generate a random salt
    salt = bcrypt.gensalt()
    # Hash password and decode back to string for database storage
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compares a plain-text password against a stored bcrypt hash string."""
    plain_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    # Returns True if password matches, False otherwise
    return bcrypt.checkpw(plain_bytes, hashed_bytes)

def create_access_token(data: dict) -> str:
    """Generates a signed JWT access token containing claims (e.g., user_id)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt