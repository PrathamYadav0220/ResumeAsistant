import sqlite3
import hashlib
from datetime import datetime

def init_db():
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password, email):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    try:
        hashed_pwd = hash_password(password)
        c.execute('INSERT INTO users (username, password, email) VALUES (?, ?, ?)',
                 (username, hashed_pwd, email))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(username, password):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    hashed_pwd = hash_password(password)
    c.execute('SELECT * FROM users WHERE username = ? AND password = ?',
             (username, hashed_pwd))
    user = c.fetchone()
    conn.close()
    return user is not None
