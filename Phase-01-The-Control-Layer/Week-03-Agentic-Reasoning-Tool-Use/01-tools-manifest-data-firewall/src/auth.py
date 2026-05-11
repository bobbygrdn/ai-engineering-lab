import sqlite3
import hashlib

DB_PATH = "users.db"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password, email=None):
    password_hash = hash_password(password)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                (username, password_hash, email)
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def authenticate_user(username, password):
    password_hash = hash_password(password)
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "SELECT id FROM users WHERE username=? AND password_hash=?",
            (username, password_hash)
        )
        row = cur.fetchone()
        return row[0] if row else None
