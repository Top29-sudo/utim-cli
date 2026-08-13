import os, json, tempfile, pytest

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _tmp(suffix='.py'):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    os.unlink(path)
    return path

def _tmp_existing(suffix='.py', content='x = 1\n'):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.write(fd, content.encode())
    os.close(fd)
    return path

# ─── 1. Syntax blocking: write_file ───────────────────────────────────────────

class TestWriteFileSyntaxBlocking:

    def test_valid_python_is_written(self):
        from utim_cli.tools import write_file
        path = _tmp('.py')
        try:
            result = write_file(path, 'x = 1\nprint(x)\n')
            assert 'Successfully created' in result
            assert os.path.exists(path)
        finally:
            if os.path.exists(path): os.unlink(path)

    def test_invalid_python_is_blocked(self):
        from utim_cli.tools import write_file
        path = _tmp('.py')
        try:
            result = write_file(path, 'def foo(\n    # unclosed\n')
            assert 'Pre-Commit Validation Failed' in result
            assert not os.path.exists(path), 'File should not exist after blocked write'
        finally:
            if os.path.exists(path): os.unlink(path)

    def test_invalid_python_does_not_overwrite_existing(self):
        from utim_cli.tools import write_file
        original = 'x = 42\n'
        path = _tmp_existing('.py', original)
        try:
            result = write_file(path, 'def broken(\n')
            assert 'Pre-Commit Validation Failed' in result
            with open(path, encoding='utf-8') as f:
                assert f.read() == original
        finally:
            if os.path.exists(path): os.unlink(path)

    def test_force_override_writes_despite_syntax_error(self):
        from utim_cli.tools import write_file
        path = _tmp('.py')
        try:
            result = write_file(path, 'def foo(\n', force=True)
            assert 'Pre-Commit Validation Failed' not in result
            assert os.path.exists(path)
        finally:
            if os.path.exists(path): os.unlink(path)

    def test_invalid_json_is_blocked(self):
        from utim_cli.tools import write_file
        path = _tmp('.json')
        try:
            result = write_file(path, '{"key": "value", bad}')
            assert 'Pre-Commit Validation Failed' in result
            assert not os.path.exists(path)
        finally:
            if os.path.exists(path): os.unlink(path)

    def test_valid_json_is_written(self):
        from utim_cli.tools import write_file
        path = _tmp('.json')
        try:
            result = write_file(path, '{"key": "value"}')
            assert 'Successfully created' in result
        finally:
            if os.path.exists(path): os.unlink(path)

# ─── 2. Syntax blocking: edit_file ────────────────────────────────────────────

class TestEditFileSyntaxBlocking:

    def test_valid_edit_is_applied(self):
        from utim_cli.tools import edit_file
        path = _tmp_existing('.py', 'x = 1\ny = 2\n')
        try:
            result = edit_file(path, old_str='x = 1', new_str='x = 99')
            assert 'Successfully edited' in result
            with open(path, encoding='utf-8') as f:
                assert 'x = 99' in f.read()
        finally:
            if os.path.exists(path): os.unlink(path)

    def test_edit_that_introduces_syntax_error_is_blocked(self):
        from utim_cli.tools import edit_file
        original = 'def foo():\n    return 1\n'
        path = _tmp_existing('.py', original)
        try:
            result = edit_file(path, old_str='return 1', new_str='return (1\n# unclosed')
            assert 'Pre-Commit Validation Failed' in result
            with open(path, encoding='utf-8') as f:
                assert f.read() == original
        finally:
            if os.path.exists(path): os.unlink(path)

    def test_batch_edit_blocked_on_syntax_error(self):
        from utim_cli.tools import edit_file
        original = 'a = 1\nb = 2\n'
        path = _tmp_existing('.py', original)
        try:
            result = edit_file(path, replacements=[
                {'old_str': 'a = 1', 'new_str': 'a = 1\ndef broken('},
                {'old_str': 'b = 2', 'new_str': 'b = 99'},
            ])
            assert 'Pre-Commit Validation Failed' in result
            with open(path, encoding='utf-8') as f:
                assert f.read() == original
        finally:
            if os.path.exists(path): os.unlink(path)

    def test_edit_force_bypass_works(self):
        from utim_cli.tools import edit_file
        path = _tmp_existing('.py', 'x = 1\n')
        try:
            result = edit_file(path, old_str='x = 1', new_str='def broken(', force=True)
            assert 'Pre-Commit Validation Failed' not in result
        finally:
            if os.path.exists(path): os.unlink(path)

# ─── 3. Command safety ────────────────────────────────────────────────────────

class TestCommandSafety:

    def test_rm_rf_is_dangerous(self):
        from utim_cli.tools import analyze_command_safety
        result = analyze_command_safety('rm -rf /')
        assert result[0] == False

    def test_safe_command_is_safe(self):
        from utim_cli.tools import analyze_command_safety
        result = analyze_command_safety('ls -la')
        assert result[0] == True

    def test_git_push_force_is_risky(self):
        from utim_cli.tools import analyze_command_safety
        result = analyze_command_safety('git push --force origin main')
        assert result[0] == False

# ─── 4. validate_syntax edge cases ───────────────────────────────────────────

class TestValidateSyntax:

    def test_returns_none_for_unknown_extension(self):
        from utim_cli.tools import validate_syntax
        assert validate_syntax('file.rb', "puts 'hello'") is None

    def test_returns_none_for_empty_py(self):
        from utim_cli.tools import validate_syntax
        assert validate_syntax('empty.py', '') is None

    def test_returns_error_string_for_bad_py(self):
        from utim_cli.tools import validate_syntax
        result = validate_syntax('bad.py', 'def foo(\n')
        assert result is not None
        assert 'Syntax Error' in result or 'Parse Error' in result

    def test_returns_none_for_valid_py(self):
        from utim_cli.tools import validate_syntax
        assert validate_syntax('ok.py', 'x = 1\n') is None

