import sqlite3
from auth import hash_password
from logger import logger
import re

DB_PATH = "users.db"

def create_memories_table():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        conn.commit()

def create_users_table():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT
            )
        """)
        conn.commit()

def create_messages_table():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        conn.commit()

def is_ambiguous_message(msg):
    ambiguous_patterns = [
        r"i need to change my password",
        r"i want to update my email",
        r"i want to change my username",
        r"update my info",
        r"change my details"
    ]
    return any(re.search(pat, msg.lower()) for pat in ambiguous_patterns)

def add_memory(user_id, category, role, content, timestamp):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO memories (user_id, category, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (user_id, category, role, content, timestamp)
        )
        conn.commit()

def load_memories(user_id):
    '''
    Load the memories from the db for the specified user. If the user has no memories, initialize with empty lists for each category.
    '''
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "SELECT category, role, content, timestamp FROM memories WHERE user_id=?",
            (user_id,)
        )
        memories = {"preferences": [], "past_issues": [], "system_context": []}
        for category, role, content, timestamp in cur.fetchall():
            if not is_ambiguous_message(content):
                memories[category].append({
                    "role": role,
                    "content": content,
                    "timestamp": timestamp
                })
        return memories

def update_email(user_id, email):
    logger.info(f"Updating email for user_id {user_id}")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE users SET email=? WHERE id=?",
            (email, user_id)
        )
        conn.commit()

def update_password(user_id, password):
    logger.info(f"Updating password for user_id {user_id}")
    password_hash = hash_password(password)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (password_hash, user_id)
        )
        conn.commit()

def update_username(user_id, username):
    logger.info(f"Updating username for user_id {user_id}")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE users SET username=? WHERE id=?",
            (username, user_id)
        )
        conn.commit()