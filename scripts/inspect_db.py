import os
import sqlite3

def check_db(path):
    print(f"Checking DB at: {path}")
    if not os.path.exists(path):
        print("  File does not exist.")
        return
    print(f"  File exists. Size: {os.path.getsize(path)} bytes")
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cursor.fetchall()]
        print(f"  Tables: {tables}")
        if 'conversations' in tables:
            cursor.execute("SELECT id, title, created_at FROM conversations;")
            convs = cursor.fetchall()
            print(f"  Conversations ({len(convs)}):")
            for c in convs:
                print(f"    - ID: {c[0]}, Title: {c[1]}, Created: {c[2]}")
        conn.close()
    except Exception as e:
        print(f"  Error reading DB: {e}")

# Check project-local
local_path = os.path.abspath(".utim/utim_local.db")
check_db(local_path)

# Check home directory
home_path = os.path.expanduser("~/.utim/utim_local.db")
check_db(home_path)
