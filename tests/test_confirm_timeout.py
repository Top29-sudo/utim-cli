import pytest
import time
from utim_cli.utim import _read_arrow_choice

def test_read_arrow_choice_auto_decline_timeout():
    options = ["Accept", "Auto-accept session", "Reject (cancel)"]
    # Pass a tiny timeout_seconds = 0.1s to test auto-decline logic without waiting
    start = time.time()
    choice_idx = _read_arrow_choice(options, timeout_seconds=0.1)
    elapsed = time.time() - start
    
    # Should auto-decline by returning index 2 (last option) in ~0.1s
    assert choice_idx == len(options) - 1
    assert elapsed >= 0.09
