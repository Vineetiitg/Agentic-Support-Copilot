"""SQLite-backed user store for authentication."""
import sqlite3
import logging
from pathlib import Path
from passlib.context import CryptContext

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DB_PATH = Path("data/users.db")


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize the user database with schema and default users."""
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Seed default users if table is empty
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            default_users = [
                ("admin", pwd_context.hash("admin123"), "admin"),
                ("user", pwd_context.hash("user123"), "user"),
            ]
            conn.executemany(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                default_users,
            )
            logger.info("Seeded default users (admin, user) into SQLite database.")
        conn.commit()
    finally:
        conn.close()


def get_user(username: str) -> dict | None:
    """Retrieve user by username."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT username, password_hash, role FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row:
            return {"username": row["username"], "password_hash": row["password_hash"], "role": row["role"]}
        return None
    finally:
        conn.close()


def create_user(username: str, password: str, role: str = "user") -> bool:
    """Create a new user. Returns True if successful."""
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, pwd_context.hash(password), role),
        )
        conn.commit()
        logger.info(f"Created user: {username} (role={role})")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"User already exists: {username}")
        return False
    finally:
        conn.close()


def list_users() -> list[dict]:
    """List all users (without password hashes)."""
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT username, role, created_at FROM users").fetchall()
        return [{"username": r["username"], "role": r["role"], "created_at": r["created_at"]} for r in rows]
    finally:
        conn.close()


# Initialize on import
init_db()
