import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), "habit_tracker.db")

def create_friends_table():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS friends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        friend_id INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, friend_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (friend_id) REFERENCES users(user_id)
    );
    """)

    conn.commit()
    conn.close()
    print("friends table created (or already exists).")

if __name__ == "__main__":
    create_friends_table()
