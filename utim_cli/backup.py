import os
import shutil
import json
import sqlite3
from utim_cli.logger import log_info, log_error, log_warning

from utim_cli.config import get_utim_dir

BACKUP_DIR = str(get_utim_dir().parent / ".utim_backup")
UTIM_DIR = str(get_utim_dir())

def is_json_valid(path: str) -> bool:
    """Check if JSON file exists and is parseable."""
    if not os.path.exists(path):
        return True
    try:
        with open(path, "r", encoding="utf-8") as f:
            json.load(f)
        return True
    except Exception:
        return False

def is_sqlite_valid(path: str) -> bool:
    """Check if SQLite DB is valid via PRAGMA integrity_check."""
    if not os.path.exists(path):
        return True
    try:
        conn = sqlite3.connect(path)
        c = conn.cursor()
        c.execute("PRAGMA integrity_check(1)")
        res = c.fetchone()
        conn.close()
        return res is not None and res[0] == "ok"
    except Exception:
        return False

def is_file_valid(path: str) -> bool:
    """Determine if a file is not corrupted based on its extension."""
    if path.endswith(".json"):
        return is_json_valid(path)
    elif path.endswith(".db"):
        return is_sqlite_valid(path)
    return True

def backup_state():
    """Backup active configuration and database files to .utim_backup/."""
    try:
        if not os.path.exists(UTIM_DIR):
            return
            
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        files_to_backup = [
            "config.json", "mcp.json", "utim_local.db", 
            "memory.json", "session_state.json"
        ]
        for f in files_to_backup:
            src = os.path.join(UTIM_DIR, f)
            dst = os.path.join(BACKUP_DIR, f)
            if os.path.exists(src):
                # Verify file is not corrupted before backing it up
                if not is_file_valid(src):
                    log_warning("backup", f"Skipping backup of corrupted file {f}")
                    continue
                
                shutil.copy2(src, dst)
                
        log_info("backup", "State backup completed successfully.")
    except Exception as e:
        log_error("backup", f"State backup failed: {e}", e)

def restore_state() -> bool:
    """Restore configuration and database files from backup if corrupt or missing."""
    try:
        if not os.path.exists(BACKUP_DIR):
            return False
            
        os.makedirs(UTIM_DIR, exist_ok=True)
        restored = False
        
        files_to_restore = [
            "config.json", "mcp.json", "utim_local.db", 
            "memory.json", "session_state.json"
        ]
        for f in files_to_restore:
            src = os.path.join(BACKUP_DIR, f)
            dst = os.path.join(UTIM_DIR, f)
            
            # Check if destination is missing or corrupted
            needs_restore = not os.path.exists(dst) or not is_file_valid(dst)
            
            if needs_restore and os.path.exists(src) and is_file_valid(src):
                shutil.copy2(src, dst)
                restored = True
                log_info("backup", f"Restored {f} from backup.")
                
        if restored:
            log_info("backup", "State backup restored successfully.")
        return restored
    except Exception as e:
        log_error("backup", f"State restoration failed: {e}", e)
        return False

