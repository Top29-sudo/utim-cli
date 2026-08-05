import os
import sys
import json
import pathlib
from utim_cli.state import STATE
from utim_cli.tools import manage_memory

def test_warnings():
    # 0. Setup: Create a mock memory.json file for the duration of this test
    mem_dir = pathlib.Path(".utim").resolve()
    mem_file = mem_dir / "memory.json"
    
    # Backup existing memory file if it exists
    backup_data = None
    file_existed = mem_file.exists()
    if file_existed:
        try:
            with open(mem_file, "r", encoding="utf-8") as f:
                backup_data = json.load(f)
        except Exception:
            pass
            
    # Write mock memory file
    mem_dir.mkdir(parents=True, exist_ok=True)
    mock_memories = {
        "secret_code": {
            "content": "Stark 3000",
            "category": "fact",
            "updated_at": "2026-06-14T11:00:00"
        },
        "girlfriend_name": {
            "content": "Girlfriend's name is Anushka, also called Puchkuli",
            "category": "fact",
            "updated_at": "2026-06-06T23:20:30"
        }
    }
    with open(mem_file, "w", encoding="utf-8") as f:
        json.dump(mock_memories, f, indent=2, ensure_ascii=False)

    try:
        # Reset state to unverified and unsynced
        STATE["is_verified"] = False
        STATE["memories_synced"] = False
        
        # 1. Try to read a sensitive memory when unverified (girlfriend_name)
        res = manage_memory("read", key="girlfriend_name")
        assert "[VERIFICATION REQUIRED]" in res
        
        # 2. Try to search sensitive query when unverified
        res = manage_memory("search", query="girlfriend")
        assert "[VERIFICATION REQUIRED]" in res
        
        # 3. Try to save a sensitive memory when unverified
        res = manage_memory("save", key="secret_code", content="new_secret_code")
        assert "[VERIFICATION REQUIRED]" in res
        
        # 4. Verify with incorrect code
        res = manage_memory("verify", query="wrong_code")
        assert "Verification failed" in res
        assert STATE["is_verified"] is False
        
        # 5. Verify with correct code
        res = manage_memory("verify", query="Stark 3000")
        assert "Verification successful" in res
        assert STATE["is_verified"] is True
        
        # 6. Read sensitive memory when verified
        res = manage_memory("read", key="girlfriend_name")
        assert "[VERIFICATION REQUIRED]" not in res
        assert "Anushka" in res
        
        # 7. Search sensitive memory when verified
        res = manage_memory("search", query="girlfriend")
        assert "[VERIFICATION REQUIRED]" not in res
        assert "Anushka" in res
        
    finally:
        # Clean up: Restore backup or delete mock file
        if file_existed and backup_data is not None:
            with open(mem_file, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
        elif mem_file.exists():
            try:
                mem_file.unlink()
            except Exception:
                pass
        
        # Reset state to unverified
        STATE["is_verified"] = False
