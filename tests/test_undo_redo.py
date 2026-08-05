import os
import shutil
import sys
from rich.console import Console
if "pytest" in sys.modules:
    import pytest
    pytest.skip("Skipping standalone script during pytest discovery", allow_module_level=True)

# Setup backup of active .utim workspace to prevent deleting user memory/config
backup_path = ".utim_backup_undoredo"
backup_exists = False
if os.path.exists(".utim"):
    if os.path.exists(backup_path):
        try:
            shutil.rmtree(backup_path)
        except Exception:
            pass
    try:
        shutil.copytree(".utim", backup_path)
        backup_exists = True
    except Exception:
        pass
    try:
        shutil.rmtree(".utim")
    except Exception:
        pass

print("Initializing DB...")
from utim_cli.server.db import init_db, DB_URL, Conversation, SessionLocal
init_db()

print(f"Verified Database URL resolved to project-local: {DB_URL}")
assert ".utim" in DB_URL, f"Expected Database URL to be project-local, got {DB_URL}"
assert os.path.exists(".utim/utim_local.db"), "Database file was not created inside .utim directory!"
print("[OK] Project-local database file successfully created.")

print("Initializing Orchestrator...")
from utim_cli.orchestrator import Orchestrator
console = Console()
orch = Orchestrator(console)

# Mock some messages
orch.messages.append({"role": "user", "content": "Mock prompt 1"})
orch.messages.append({"role": "assistant", "content": "Mock assistant reply 1", "tool_calls": []})

# Persist and check session creation
orch._persist_messages()
import time
time.sleep(0.5) # Allow background persistence thread to finish

db = SessionLocal()
convs = db.query(Conversation).all()
assert len(convs) > 0, "No conversation session persisted in database!"
session_id = convs[0].id
print(f"[OK] Successfully persisted conversation session ID: {session_id}")

# Verify database fields
conv = convs[0]
print(f"Conversation stored columns:")
print(f"  messages count: {len(conv.messages)}")
print(f"  turn_history: {conv.turn_history}")
print(f"  redo_history: {conv.redo_history}")
db.close()

# Test mock file changes with turn history
test_file = "test_dummy.txt"
if os.path.exists(test_file):
    os.remove(test_file)

print("Simulating a code-changing turn...")
# Initial write
with open(test_file, "w") as f:
    f.write("Original content")

# Capture before state
orch._turn_changes = [{
    "action": "edit_file",
    "path": test_file,
    "before": "Original content",
    "after": "Modified content"
}]

# Apply after state
with open(test_file, "w") as f:
    f.write("Modified content")

# Save turn
orch.turn_history.append({
    "user_msg": "Edit dummy text",
    "msg_start": 2,
    "msg_end": 4,
    "messages": [
        {"role": "user", "content": "Edit dummy text"},
        {"role": "assistant", "content": "I edited test_dummy.txt"}
    ],
    "changes": list(orch._turn_changes)
})
orch._turn_changes = []

print(f"File content before undo: '{open(test_file).read()}'")
assert open(test_file).read() == "Modified content"

print("Triggering UNDO...")
res = orch.undo_last_turn()
time.sleep(0.5) # Wait for persist thread

print(f"File content after undo: '{open(test_file).read()}'")
assert open(test_file).read() == "Original content", "Undo did not revert the file content!"
print("[OK] Undo successfully reverted file changes.")

print("Triggering REDO...")
res2 = orch.redo_last_undone_turn()
time.sleep(0.5) # Wait for persist thread

print(f"File content after redo: '{open(test_file).read()}'")
assert open(test_file).read() == "Modified content", "Redo did not re-apply the file content!"
print("[OK] Redo successfully re-applied file changes.")

# Verify persistent states inside Database
db = SessionLocal()
conv = db.query(Conversation).filter(Conversation.id == orch.session_id).first()
assert conv.turn_history is not None
assert len(conv.turn_history) == 1, f"Expected 1 turn persisted, got {len(conv.turn_history)}"
print("[OK] Database turn_history verified successfully.")
db.close()

# Cleanup
if os.path.exists(test_file):
    os.remove(test_file)
try:
    from utim_cli.server.db import engine
    engine.dispose()
except Exception:
    pass
if os.path.exists(".utim"):
    try:
        shutil.rmtree(".utim")
    except Exception:
        pass
if backup_exists and os.path.exists(backup_path):
    try:
        shutil.copytree(backup_path, ".utim")
        shutil.rmtree(backup_path)
    except Exception:
        pass

print("\nALL TESTS PASSED SUCCESSFULLY!")
