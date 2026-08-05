import os
import tempfile
import zipfile
from pathlib import Path
from utim_cli.share import ShareManager

def test_share_manager_zip_and_exclude():
    # Create a temp directory to act as workspace
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Setup files/folders
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "index.js").write_text("console.log('hello');", encoding='utf-8')
        
        nm_dir = tmp_path / "node_modules"
        nm_dir.mkdir()
        (nm_dir / "lodash.js").write_text("module.exports = {};", encoding='utf-8')
        
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]\nrepositoryformatversion = 0", encoding='utf-8')
        
        pycache_dir = tmp_path / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "utils.pyc").write_bytes(b"python bytecode")
        
        utim_dir = tmp_path / ".utim"
        utim_dir.mkdir()
        (utim_dir / "config.json").write_text("{}", encoding='utf-8')
        
        utim_tmp_dir = tmp_path / ".utim_tmp"
        utim_tmp_dir.mkdir()
        (utim_tmp_dir / "cache.txt").write_text("cache", encoding='utf-8')
        
        # Instantiate ShareManager
        manager = ShareManager(workspace_path=str(tmp_path))
        
        # Check defaults/initial states
        assert len(manager.get_all()) == 0
        
        # Create share excluding node_modules, .git, and __pycache__ and .utim
        chat_messages = [
            {"role": "system", "content": "You are a coding assistant"},
            {"role": "user", "content": "Hello world"},
            {"role": "assistant", "content": "Hi!"}
        ]
        
        from unittest.mock import patch, MagicMock
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": True, "link": f"https://api.utim.dev/shares/download/{tmp_path.name}_share_test123", "expires_at": "2026-07-08T22:00:00Z"}

        with patch('requests.post', return_value=mock_resp):
            rec = manager.create_share(
                exclude_keys=["node_modules", ".git", "__pycache__", ".utim"],
                expiry_hours=1.0,
                chat_messages=chat_messages
            )
        
        # Verify share record
        assert rec.name == tmp_path.name
        assert rec.excluded == ["node_modules", ".git", "__pycache__", ".utim"]
        assert not rec.is_expired()
        
        # Verify zip file exists and contains correct files
        zip_path = Path(rec.file_path)
        assert zip_path.exists()
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            namelist = zipf.namelist()
            print("Zip contents:", namelist)
            
            # Should contain chat_history.md
            assert "chat_history.md" in namelist
            
            # Should contain src/index.js
            assert "src/index.js" in namelist
            
            # Should NOT contain node_modules files, .git files, or __pycache__
            assert not any("node_modules" in name for name in namelist)
            assert not any(".git" in name for name in namelist)
            assert not any("__pycache__" in name for name in namelist)
            assert not any(".utim" in name for name in namelist)
            assert not any(".utim_tmp" in name for name in namelist)
            
            # Verify chat history content
            chat_hist = zipf.read("chat_history.md").decode('utf-8')
            assert "Hello world" in chat_hist
            assert "Hi!" in chat_hist
            
        # Verify that if .utim is NOT excluded, it is included in the zip
        with patch('requests.post', return_value=mock_resp):
            rec_no_excl = manager.create_share(
                exclude_keys=["node_modules", ".git", "__pycache__"],
                expiry_hours=1.0,
                chat_messages=chat_messages
            )
        with zipfile.ZipFile(Path(rec_no_excl.file_path), 'r') as zipf:
            namelist_no_excl = zipf.namelist()
            assert any(".utim/config.json" in name for name in namelist_no_excl)
            assert any(".utim_tmp/cache.txt" in name for name in namelist_no_excl)

        # Setup custom test files/folders to omit
        (src_dir / "secret_custom.txt").write_text("my custom secret key", encoding='utf-8')
        secret_f = src_dir / "secret_folder"
        secret_f.mkdir()
        (secret_f / "custom.txt").write_text("another custom secret", encoding='utf-8')
        
        # Test custom relative path and folder exclusions
        with patch('requests.post', return_value=mock_resp):
            rec_custom = manager.create_share(
                exclude_keys=["src/secret_custom.txt", "src/secret_folder"],
                expiry_hours=1.0,
                chat_messages=chat_messages
            )
        with zipfile.ZipFile(Path(rec_custom.file_path), 'r') as zipf:
            namelist_custom = zipf.namelist()
            assert "src/index.js" in namelist_custom
            assert not any("secret_custom.txt" in name for name in namelist_custom)
            assert not any("secret_folder" in name for name in namelist_custom)

        # Verify search
        found = manager.search(rec.id)
        assert len(found) == 1
        assert found[0].id == rec.id
        
        # Verify delete
        manager.delete(rec.id)
        assert not zip_path.exists()
        manager.delete(rec_no_excl.id)
        manager.delete(rec_custom.id)
        assert len(manager.get_all()) == 0
