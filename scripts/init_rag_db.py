import sqlite3
from datetime import datetime
import uuid
import json

def init_rag_database():
    """Initialize the RAG intelligence database with core structure and analytical rules."""
    conn = sqlite3.connect('.utim/rag_intelligence.db')
    c = conn.cursor()
    
    # Create core tables
    c.execute('''
        CREATE TABLE IF NOT EXISTS experiences (
            id TEXT PRIMARY KEY,
            type TEXT,
            category TEXT,
            content TEXT,
            timestamp TEXT,
            context TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS analytical_rules (
            id TEXT PRIMARY KEY,
            rule_name TEXT,
            rule_description TEXT,
            priority INTEGER
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS failures (
            id TEXT PRIMARY KEY,
            task_id TEXT,
            failure_type TEXT,
            error_description TEXT,
            correction_applied TEXT,
            timestamp TEXT
        )
    ''')
    
    # Prewritten analytical rules for intelligence
    analytical_rules = [
        ("goal_first", "Always identify true objective before proposing solutions", 1),
        ("constraint_check", "Map all physical/logical constraints before solution generation", 2),
        ("feasibility_verify", "Verify each solution actually works in reality", 3),
        ("assumption_audit", "Check assumptions before responding", 4),
        ("surface_bias_check", "Avoid focusing on literal words vs underlying intent", 5),
        ("solution_alignment", "Every proposed action must directly achieve the stated goal", 6),
        ("reality_test", "Apply physics and common sense validation to all suggestions", 7),
    ]
    
    for rule in analytical_rules:
        try:
            c.execute("INSERT INTO analytical_rules (id, rule_name, rule_description, priority) VALUES (?, ?, ?, ?)", 
                   (str(uuid.uuid4()), rule[0], rule[1], rule[2]))
        except sqlite3.IntegrityError:
            pass  # Rule already exists
    
    # Store initial experience
    c.execute("INSERT INTO experiences (id, type, category, content, timestamp, context) VALUES (?, ?, ?, ?, ?, ?)",
           (str(uuid.uuid4()), "system_init", "setup", 
            "RAG intelligence database initialized with analytical reasoning framework",
            datetime.now().isoformat(),
            json.dumps({"rules_count": len(analytical_rules)})))
    
    conn.commit()
    conn.close()
    print("[OK] RAG DB created with analytical rules framework")
    return True

if __name__ == '__main__':
    init_rag_database()