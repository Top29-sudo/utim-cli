import sys
import os
import argparse
import sqlite3
from datetime import datetime

def store(category, content):
    db_path = os.path.join('.utim', 'rag_intelligence.db')
    if not os.path.exists('.utim'):
        os.makedirs('.utim', exist_ok=True)
        
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    import uuid
    exp_id = uuid.uuid4().hex
    
    # Ensure tables exist (unified schema)
    c.execute('''
        CREATE TABLE IF NOT EXISTS experiences (
            id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
            type TEXT,
            category TEXT,
            content TEXT,
            timestamp TEXT,
            context TEXT,
            priority INTEGER DEFAULT 0
        )
    ''')
    
    timestamp = datetime.now().isoformat()
    c.execute(
        "INSERT INTO experiences (id, type, category, content, timestamp) VALUES (?, ?, ?, ?, ?)",
        (exp_id, 'learning', category, content, timestamp)
    )
    conn.commit()
    conn.close()
    
    try:
        from utim_cli.vector_memory import get_experiences_memory
        vm = get_experiences_memory()
        if vm:
            vm.add_text(
                text_id=exp_id,
                content=content,
                metadata={"category": category, "timestamp": timestamp, "type": "learning"}
            )
    except Exception as e:
        print(f"Warning: Failed to sync with vector memory: {e}")

    print(f"[OK] Stored experience under category '{category}'")

def list_experiences():
    db_path = os.path.join('.utim', 'rag_intelligence.db')
    if not os.path.exists(db_path):
        print("No RAG database found.")
        return
        
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        c.execute("SELECT id, category, content, timestamp FROM experiences ORDER BY timestamp DESC")
        rows = c.fetchall()
        if not rows:
            print("No stored experiences.")
        else:
            print(f"Stored Experiences ({len(rows)}):")
            for r in rows:
                print(f"[{r['timestamp']}] [{r['category']}] (ID: {r['id'][:8]})")
                print(f"  {r['content']}")
                print("-" * 40)
    except sqlite3.OperationalError:
        print("Experiences table does not exist yet.")
    conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Manage UTIM RAG DB experiences")
    parser.add_argument('--list', action='store_true', help="List all stored experiences")
    parser.add_argument('--category', type=str, help="Category of experience")
    parser.add_argument('--content', type=str, help="Content of experience")
    
    args = parser.parse_args()
    
    if args.list:
        list_experiences()
    elif args.category and args.content:
        store(args.category, args.content)
    else:
        # Default behavior: list experiences if no args
        list_experiences()
