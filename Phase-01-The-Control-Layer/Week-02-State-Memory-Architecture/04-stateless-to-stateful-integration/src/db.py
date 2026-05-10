import sqlite3

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
            memories[category].append({
                "role": role,
                "content": content,
                "timestamp": timestamp
            })
        return memories