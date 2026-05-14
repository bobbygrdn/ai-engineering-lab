from llm_utils import classify_message
from auth import hash_password
from logger import logger
from models import MemoryEntry, MemoryCategory
from pydantic import ValidationError
import sqlite3
import time
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

def create_tickets_table():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ticket_id TEXT UNIQUE NOT NULL,
                issue_description TEXT,
                status TEXT DEFAULT 'open',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
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

def parse_and_writeback(role: str, response: str, user_id: int, model: str = "gpt-4o-mini"):
    '''
    Parse the LLM response and write back any new facts or updates to the memories table in the db.
    '''
    try:
        new_fact = MemoryEntry(role=role, content=response, timestamp=int(time.time()))
    except ValidationError as e:
        logger.error(f"Error creating MemoryEntry for response '{response}': {e}")
        return

    classification = classify_message(response, model)

    preference_keywords = ["prefer", "like", "dislike", "want", "please keep", "please avoid", "i do not like", "i would rather", "i wish"]
    is_preference = role == "user" and any(keyword in response.lower() for keyword in preference_keywords)
    if is_preference:
        category = MemoryCategory.PREFERENCES
    else:
        try:
            category = MemoryCategory[classification.upper()]
            logger.info(f"Classified new fact '{response}' into category: {category.value}")
        except KeyError:
            category = MemoryCategory.PAST_ISSUES
            logger.warning(f"Classification '{classification}' not recognized. Defaulting to 'past_issues' category.")

    add_memory(user_id, category.value, new_fact.role, new_fact.content, new_fact.timestamp)

def update_email(user_id, email, ticket_id=None):
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        raise Exception("Invalid email format")
    logger.info(f"Updating email for user_id {user_id}")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE users SET email=? WHERE id=?",
            (email, user_id)
        )
        conn.commit()
        cur = conn.execute(
            "SELECT email FROM users WHERE id=?",
            (user_id,)
        )
        updated_email = cur.fetchone()[0]
        if updated_email == email:
            return True
        else:
            raise Exception("Email update failed")

def update_password(user_id, password, ticket_id=None):
    if len(password) < 6 or password == "":
        raise Exception("Password must be at least 6 characters long and not empty")
    logger.info(f"Updating password for user_id {user_id}")
    password_hash = hash_password(password)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (password_hash, user_id)
        )
        conn.commit()
        cur = conn.execute(
            "SELECT password_hash FROM users WHERE id=?",
            (user_id,)
        )
        updated_hash = cur.fetchone()[0]
        if updated_hash == password_hash:
            return True
        else:
            raise Exception("Password update failed")

def update_username(user_id, username, ticket_id=None):
    if len(username) < 3 or username == "":
        raise Exception("Username must be at least 3 characters long and not empty")
    logger.info(f"Updating username for user_id {user_id}")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE users SET username=? WHERE id=?",
            (username, user_id)
        )
        conn.commit()
        cur = conn.execute(
            "SELECT username FROM users WHERE id=?",
            (user_id,)
        )
        updated_username = cur.fetchone()[0]
        if updated_username == username:
            return True
        else:
            raise Exception("Username update failed")

def add_ticket(user_id, ticket_id, issue_description, status="open"):
    timestamp = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO tickets (user_id, ticket_id, issue_description, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, ticket_id, issue_description, status, timestamp, timestamp)
        )
        conn.commit()

def get_ticket_by_id(ticket_id):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "SELECT id, user_id, ticket_id, issue_description, status, created_at, updated_at FROM tickets WHERE ticket_id=?",
            (ticket_id,)
        )
        row = cur.fetchone()
        if row:
            return {
                "id": row[0],
                "user_id": row[1],
                "ticket_id": row[2],
                "issue_description": row[3],
                "status": row[4],
                "created_at": row[5],
                "updated_at": row[6]
            }
        else:
            return None