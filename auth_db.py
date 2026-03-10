import sqlite3
import bcrypt

DB_FILE = "users.db"

def init_auth_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def get_password_hash(password):
    # Use raw bcrypt to avoid passlib python 3.13 internal loading bug
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain_password, hashed_password):
    pwd_bytes = plain_password.encode('utf-8')
    hash_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(pwd_bytes, hash_bytes)

def create_user(username, password, role="junior"):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    hashed_password = get_password_hash(password)
    try:
        c.execute('INSERT INTO users (username, hashed_password, role) VALUES (?, ?, ?)', (username, hashed_password, role))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success

def get_user(username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT username, hashed_password, role FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"username": row[0], "hashed_password": row[1], "role": row[2]}
    return None
