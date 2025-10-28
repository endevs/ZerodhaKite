
import sqlite3

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_db_connection()
    conn.execute('DROP TABLE IF EXISTS users')
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mobile TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            email_verified BOOLEAN NOT NULL DEFAULT 0,
            app_key TEXT,
            app_secret TEXT,
            otp TEXT,
            otp_expiry DATETIME
        )
    """)
    conn.commit()
    conn.close()

if __name__ == '__main__':
    create_tables()
