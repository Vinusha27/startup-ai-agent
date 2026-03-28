import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_DIRECTORY = PROJECT_ROOT / "database"
DATABASE_PATH = DATABASE_DIRECTORY / "database.db"


def get_connection() -> sqlite3.Connection:
    """Open a SQLite connection with rows addressable by column name."""
    DATABASE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """Initialize all SQLite tables required by the app."""
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_investors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                investor_name TEXT NOT NULL,
                firm_name TEXT NOT NULL,
                profile_url TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'To Contact',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )
        connection.commit()


class User(UserMixin):
    """User model backed by SQLite and compatible with Flask-Login."""

    def __init__(self, id: int, name: str, email: str, password_hash: str, created_at: str) -> None:
        self.id = str(id)
        self.name = name
        self.email = email
        self.password_hash = password_hash
        self.created_at = created_at

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "User":
        """Build a User instance from a SQLite row."""
        return cls(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            password_hash=row["password_hash"],
            created_at=row["created_at"],
        )

    @classmethod
    def get_by_id(cls, user_id: str) -> Optional["User"]:
        """Fetch a user by primary key."""
        with get_connection() as connection:
            row = connection.execute(
                "SELECT id, name, email, password_hash, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return cls.from_row(row) if row else None

    @classmethod
    def get_by_email(cls, email: str) -> Optional["User"]:
        """Fetch a user by email address."""
        with get_connection() as connection:
            row = connection.execute(
                "SELECT id, name, email, password_hash, created_at FROM users WHERE email = ?",
                (email.lower().strip(),),
            ).fetchone()
        return cls.from_row(row) if row else None

    @classmethod
    def create(cls, name: str, email: str, password: str) -> "User":
        """Create and return a new user record."""
        normalized_email = email.lower().strip()
        password_hash = generate_password_hash(password)

        with get_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name.strip(), normalized_email, password_hash),
            )
            connection.commit()
            user_id = cursor.lastrowid

        return cls.get_by_id(str(user_id))

    def verify_password(self, password: str) -> bool:
        """Validate a plaintext password against the stored hash."""
        return check_password_hash(self.password_hash, password)


class SavedInvestor:
    """CRM model for investor records saved by authenticated users."""

    STATUS_OPTIONS = ["To Contact", "Contacted", "Meeting Scheduled", "Rejected"]

    def __init__(
        self,
        id: int,
        user_id: int,
        investor_name: str,
        firm_name: str,
        profile_url: str,
        notes: str,
        status: str,
        created_at: str,
    ) -> None:
        self.id = id
        self.user_id = user_id
        self.investor_name = investor_name
        self.firm_name = firm_name
        self.profile_url = profile_url
        self.notes = notes
        self.status = status
        self.created_at = created_at

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "SavedInvestor":
        """Build a SavedInvestor instance from a SQLite row."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            investor_name=row["investor_name"],
            firm_name=row["firm_name"],
            profile_url=row["profile_url"],
            notes=row["notes"],
            status=row["status"],
            created_at=row["created_at"],
        )

    def to_dict(self) -> Dict[str, str]:
        """Serialize a saved investor into JSON-friendly primitives."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "investor_name": self.investor_name,
            "firm_name": self.firm_name,
            "profile_url": self.profile_url,
            "notes": self.notes,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def list_by_user(cls, user_id: str) -> List["SavedInvestor"]:
        """Return all CRM entries for a user, newest first."""
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, user_id, investor_name, firm_name, profile_url, notes, status, created_at
                FROM saved_investors
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (user_id,),
            ).fetchall()
        return [cls.from_row(row) for row in rows]

    @classmethod
    def get_by_id_and_user(cls, saved_investor_id: str, user_id: str) -> Optional["SavedInvestor"]:
        """Fetch a saved investor that belongs to a given user."""
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT id, user_id, investor_name, firm_name, profile_url, notes, status, created_at
                FROM saved_investors
                WHERE id = ? AND user_id = ?
                """,
                (saved_investor_id, user_id),
            ).fetchone()
        return cls.from_row(row) if row else None

    @classmethod
    def find_existing(
        cls, user_id: str, investor_name: str, firm_name: str, profile_url: str
    ) -> Optional["SavedInvestor"]:
        """Find an existing saved investor to avoid duplicate CRM entries."""
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT id, user_id, investor_name, firm_name, profile_url, notes, status, created_at
                FROM saved_investors
                WHERE user_id = ? AND investor_name = ? AND firm_name = ? AND profile_url = ?
                """,
                (user_id, investor_name.strip(), firm_name.strip(), profile_url.strip()),
            ).fetchone()
        return cls.from_row(row) if row else None

    @classmethod
    def create(
        cls,
        user_id: str,
        investor_name: str,
        firm_name: str,
        profile_url: str,
        notes: str = "",
        status: str = "To Contact",
    ) -> "SavedInvestor":
        """Create a saved investor entry or return the existing duplicate."""
        existing = cls.find_existing(user_id, investor_name, firm_name, profile_url)
        if existing:
            return existing

        final_status = status if status in cls.STATUS_OPTIONS else "To Contact"
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO saved_investors (user_id, investor_name, firm_name, profile_url, notes, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    investor_name.strip(),
                    firm_name.strip(),
                    profile_url.strip() or "Unknown",
                    notes.strip(),
                    final_status,
                ),
            )
            connection.commit()
            saved_investor_id = cursor.lastrowid

        return cls.get_by_id_and_user(str(saved_investor_id), user_id)

    @classmethod
    def update(cls, saved_investor_id: str, user_id: str, notes: str, status: str) -> None:
        """Update CRM notes and status for a saved investor."""
        final_status = status if status in cls.STATUS_OPTIONS else "To Contact"
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE saved_investors
                SET notes = ?, status = ?
                WHERE id = ? AND user_id = ?
                """,
                (notes.strip(), final_status, saved_investor_id, user_id),
            )
            connection.commit()
