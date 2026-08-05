import os
import json
import uuid
import datetime
import zipfile
import requests
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from utim_cli.config import get_utim_dir

# Constants
SHARES_DIR = get_utim_dir() / "shares"
SHARES_META_FILE = get_utim_dir() / "shares.json"

# Default exclude categories and their descriptions
EXCLUDE_OPTIONS = [
    {"key": "node_modules", "name": "node_modules", "desc": "Node.js dependencies"},
    {"key": ".git", "name": ".git", "desc": "Git repository history"},
    {"key": "__pycache__", "name": "__pycache__", "desc": "Python bytecode cache"},
    {"key": "venv", "name": "venv / .venv", "desc": "Python virtual environments"},
    {"key": "dist", "name": "dist / build", "desc": "Compiled build/distribution folders"},
    {"key": ".next", "name": ".next / .nuxt", "desc": "Next.js / Nuxt.js dev & build caches"},
    {"key": "target", "name": "target", "desc": "Rust cargo build artifacts"},
    {"key": ".env", "name": ".env / configuration", "desc": "Environment secrets and local configs"},
    {"key": ".utim", "name": ".utim / .utim_tmp", "desc": "UTIM system logs, database and caches"},
]

# Expiry options in hours
EXPIRY_OPTIONS = [
    {"label": "15 Minutes", "hours": 0.25},
    {"label": "1 Hour", "hours": 1.0},
    {"label": "4 Hours", "hours": 4.0},
    {"label": "24 Hours", "hours": 24.0},
    {"label": "3 Days", "hours": 72.0},
    {"label": "7 Days", "hours": 168.0},
]

class ShareRecord:
    def __init__(self, id: str, name: str, created_at: str, expires_at: str, link: str, file_path: str, excluded: List[str], share_type: str = "chat_project"):
        self.id = id
        self.name = name
        self.created_at = created_at
        self.expires_at = expires_at
        self.link = link
        self.file_path = file_path
        self.excluded = excluded
        self.share_type = share_type

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "link": self.link,
            "file_path": self.file_path,
            "excluded": self.excluded,
            "share_type": self.share_type
        }

    @classmethod
    def from_dict(cls, data: Dict):
        return cls(
            id=data["id"],
            name=data["name"],
            created_at=data["created_at"],
            expires_at=data["expires_at"],
            link=data["link"],
            file_path=data["file_path"],
            excluded=data.get("excluded", []),
            share_type=data.get("share_type", "chat_project")
        )

    def is_expired(self) -> bool:
        try:
            exp = datetime.datetime.fromisoformat(self.expires_at)
            now = datetime.datetime.now(datetime.timezone.utc)
            return now > exp
        except Exception:
            return True

    def time_remaining(self) -> str:
        if self.is_expired():
            return "Expired"
        try:
            exp = datetime.datetime.fromisoformat(self.expires_at)
            now = datetime.datetime.now(datetime.timezone.utc)
            delta = exp - now
            
            secs = int(delta.total_seconds())
            if secs < 60:
                return f"{secs}s left"
            mins = secs // 60
            if mins < 60:
                return f"{mins}m left"
            hours = mins // 60
            if hours < 24:
                return f"{hours}h {mins % 60}m left"
            days = hours // 24
            return f"{days}d {hours % 24}h left"
        except Exception:
            return "Unknown"

def print_progress_bar(percentage: float, prefix: str = ""):
    import sys
    bar_width = 40
    filled = int(round((percentage / 100.0) * bar_width))
    filled = min(bar_width, max(0, filled))
    
    # Check if the output encoding supports the block characters
    encoding = getattr(sys.__stdout__, 'encoding', None) or 'utf-8'
    try:
        "█".encode(encoding)
        fill_char = "█"
        empty_char = "░"
    except UnicodeEncodeError:
        fill_char = "#"
        empty_char = "-"
        
    bar = fill_char * filled + empty_char * (bar_width - filled)
    msg = f"\r  {prefix} [{bar}] {percentage:.2f}%"
    try:
        sys.__stdout__.write(msg)
        sys.__stdout__.flush()
    except UnicodeEncodeError:
        # If write fails with unicode, fall back to purely ASCII representation
        try:
            ascii_bar = "#" * filled + "-" * (bar_width - filled)
            ascii_msg = f"\r  {prefix} [{ascii_bar}] {percentage:.2f}%"
            sys.__stdout__.write(ascii_msg)
            sys.__stdout__.flush()
        except Exception:
            pass
    except Exception:
        pass


def is_path_excluded(rel_path: Path, exclude_names: List[str]) -> bool:
    """
    Check if a relative path matches any exclusion.
    Supports exact path match, directory descendants matching, and component matching.
    """
    rel_posix = rel_path.as_posix().lower()
    for excl in exclude_names:
        # Convert excl to posix format for uniform matching
        try:
            excl_posix = Path(excl).as_posix().lower()
        except Exception:
            excl_posix = excl.lower()
        
        if not excl_posix:
            continue
            
        # 1. Exact match (file or folder)
        if rel_posix == excl_posix:
            return True
        # 2. Part match for parent directories (so if "src/temp_files" is excluded, "src/temp_files/foo.txt" is excluded)
        if rel_posix.startswith(excl_posix + "/"):
            return True
        # 3. Component-wise matching (for simple names like "node_modules")
        if any(part.lower() == excl_posix for part in rel_path.parts):
            return True
            
    return False


class ShareManager:
    def __init__(self, workspace_path: str = "."):
        self.workspace_path = Path(workspace_path).resolve()
        self.shares_dir = self.workspace_path / SHARES_DIR
        self.meta_file = self.workspace_path / SHARES_META_FILE
        self.shares_dir.mkdir(parents=True, exist_ok=True)
        self._load_meta()

    def _load_meta(self):
        self.records: Dict[str, ShareRecord] = {}
        if self.meta_file.exists():
            try:
                with open(self.meta_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data:
                        rec = ShareRecord.from_dict(item)
                        self.records[rec.id] = rec
            except Exception:
                # Fallback to empty if corrupted
                pass

    def _save_meta(self):
        try:
            data = [rec.to_dict() for rec in self.records.values()]
            with open(self.meta_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get_all(self) -> List[ShareRecord]:
        # Return sorted by created_at descending
        return sorted(self.records.values(), key=lambda r: r.created_at, reverse=True)

    def search(self, query: str) -> List[ShareRecord]:
        q = query.lower().strip()
        all_records = self.get_all()
        if not q:
            return all_records
        
        filtered = []
        for r in all_records:
            if q in r.name.lower() or q in r.id.lower() or q in r.link.lower() or any(q in excl.lower() for excl in r.excluded):
                filtered.append(r)
        return filtered

    def delete(self, share_id: str) -> bool:
        if share_id in self.records:
            rec = self.records[share_id]
            # Try to delete the zip file locally
            zip_p = Path(rec.file_path)
            if zip_p.exists():
                try:
                    zip_p.unlink()
                except Exception:
                    pass
            
            # Send delete request to server to clean up server storage instantly
            try:
                server_url = os.getenv("UTIM_SERVER_URL", "https://api.utim.dev")
                if server_url:
                    server_url = server_url.rstrip("/")
                    url = f"{server_url}/shares/delete/{share_id}"
                    requests.delete(url, timeout=10)
            except Exception:
                pass
            
            # Remove from meta
            del self.records[share_id]
            self._save_meta()
            return True
        return False

    def create_share(self, exclude_keys: List[str], expiry_hours: float, chat_messages: List[Dict], share_type: str = "chat_project") -> ShareRecord:
        share_id = f"share_{uuid.uuid4().hex[:12]}"
        created_at = datetime.datetime.now(datetime.timezone.utc)
        expires_at = created_at + datetime.timedelta(hours=expiry_hours)

        # Name of workspace
        workspace_name = self.workspace_path.name or "workspace"
        zip_filename = f"{workspace_name}_{share_id}.zip"
        zip_filepath = self.shares_dir / zip_filename

        # Exclude folders
        exclude_names = []
        for key in exclude_keys:
            # Map categories to actual folder names to filter
            if key == "venv":
                exclude_names.extend(["venv", ".venv", "env", ".env-venv"])
            elif key == "dist":
                exclude_names.extend(["dist", "build", "out", "target-distribution"])
            elif key == ".next":
                exclude_names.extend([".next", ".nuxt", ".expo"])
            elif key == ".env":
                exclude_names.extend([".env", ".env.local", ".env.development", ".env.production"])
            elif key == ".utim":
                exclude_names.extend([".utim", ".utim_tmp"])
            else:
                try:
                    p = Path(key)
                    if p.is_absolute():
                        try:
                            p = p.relative_to(self.workspace_path)
                        except ValueError:
                            # if it's absolute but outside workspace, keep it absolute or resolved
                            pass
                    exclude_names.append(p.as_posix())
                except Exception:
                    exclude_names.append(key)

        # Generate markdown chat history
        chat_history_content = self._format_chat_history(chat_messages)
        
        # Zip files
        self._zip_workspace(zip_filepath, exclude_names, chat_history_content, share_type, exclude_keys)

        # Upload and get link
        import sys
        size_mb = zip_filepath.stat().st_size / (1024 * 1024)
        sys.__stdout__.write(f"  Uploading shared package to server ({size_mb:.2f} MB)...")
        sys.__stdout__.flush()
        link = self._upload_file(zip_filepath, expiry_hours)
        sys.__stdout__.write(" Done!\n")
        sys.__stdout__.flush()

        rec = ShareRecord(
            id=share_id,
            name=workspace_name,
            created_at=created_at.isoformat(),
            expires_at=expires_at.isoformat(),
            link=link,
            file_path=str(zip_filepath),
            excluded=exclude_keys,
            share_type=share_type
        )

        self.records[share_id] = rec
        self._save_meta()
        return rec

    def _format_chat_history(self, messages: List[Dict]) -> str:
        md = []
        md.append("# UTIM CLI Chat History\n")
        md.append(f"Shared Workspace: `{self.workspace_path.name}`\n")
        md.append(f"Export Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        md.append("---\n\n")
        
        has_messages = False
        for msg in messages:
            role = str(msg.get("role") or "").lower()
            content = msg.get("content") or ""
            
            # Only include actual User prompts and Assistant responses
            if role not in ("user", "assistant"):
                continue
                
            # Safely extract text if content is a list
            if isinstance(content, list):
                text = "\n".join(p.get("text", "") for p in content if isinstance(p, dict) and "text" in p)
            else:
                text = str(content)
                
            # Skip empty messages
            if not text.strip():
                continue
                
            has_messages = True
            if role == "user":
                md.append(f"### 👤 User\n\n{text}\n\n")
            elif role == "assistant":
                md.append(f"### 🤖 Assistant\n\n{text}\n\n")
                
            md.append("---\n\n")
            
        if not has_messages:
            md.append("*No conversation history.*")
            
        return "".join(md)

    def _generate_share_readme(self, exclude_keys: List[str]) -> str:
        md = []
        md.append("# UTIM Shared Workspace Instructions\n\n")
        md.append("This project workspace was packaged and shared via UTIM CLI.\n")
        md.append("To keep the package size minimal and protect sensitive secrets, some files and folders were omitted.\n\n")
        md.append("## 📦 How to Reinstall Omitted Packages & Files\n\n")
        
        reinstall_guides = {
            "node_modules": "- **node_modules**: Omitted Node.js package dependencies. Run `npm install` in the project root directory to restore them.",
            "venv": "- **venv / .venv**: Omitted Python virtual environment. Run `python -m venv venv` to recreate, activate it, and run `pip install -r requirements.txt` to restore dependencies.",
            ".env": "- **.env**: Omitted environment configuration secrets. Create a new local `.env` file in the root directory and define your API keys and parameters.",
            "__pycache__": "- **__pycache__**: Omitted Python bytecode caches. These will be automatically regenerated by Python when running your scripts.",
            "dist": "- **dist / build**: Omitted compiled distribution/build artifacts. Run your project build command (e.g. `npm run build` or `python -m build`) to rebuild.",
            ".next": "- **.next**: Omitted Next.js/Nuxt.js build caches. These will be regenerated automatically during the next project run or build.",
            "target": "- **target**: Omitted Rust compilation build artifacts. Run `cargo build` in the project directory to rebuild.",
        }

        for key in exclude_keys:
            guide = reinstall_guides.get(key, f"- **{key}**: Omitted file/directory.")
            md.append(f"{guide}\n")
            
        md.append("\n---\n")
        md.append("Shared with UTIM CLI (https://utim.dev)\n")
        return "".join(md)

    def _zip_workspace(self, output_zip_path: Path, exclude_names: List[str], chat_history: str, share_type: str, exclude_keys: List[str]):
        # Calculate total files for progress calculation
        total_files = 0
        if share_type in ("project", "chat_project"):
            for root, dirs, files in os.walk(self.workspace_path):
                dirs[:] = [d for d in dirs if not is_path_excluded(Path(root).relative_to(self.workspace_path) / d, exclude_names)]
                for file in files:
                    if file.endswith(('.pyc', '.pyo', '.pyd')):
                        continue
                    full_path = Path(root) / file
                    rel_path = full_path.relative_to(self.workspace_path)
                    if is_path_excluded(rel_path, exclude_names):
                        continue
                    if full_path.resolve() == output_zip_path.resolve():
                        continue
                    total_files += 1

        if share_type in ("chat", "chat_project"):
            total_files += 1
        if share_type in ("project", "chat_project") and exclude_keys:
            total_files += 1

        total_files = max(1, total_files)
        zipped_count = 0

        with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 1. Add chat history if requested
            if share_type in ("chat", "chat_project"):
                zipf.writestr("chat_history.md", chat_history)
                zipped_count += 1
                print_progress_bar(100.0 * zipped_count / total_files, "Compressing:")

            # 2. Add workspace files if requested
            if share_type in ("project", "chat_project"):
                # Write the custom README explaining how to reinstall omitted packages
                if exclude_keys:
                    readme_content = self._generate_share_readme(exclude_keys)
                    zipf.writestr("README.md", readme_content)
                    zipped_count += 1
                    print_progress_bar(100.0 * zipped_count / total_files, "Compressing:")

                for root, dirs, files in os.walk(self.workspace_path):
                    # Filter directories in-place to prevent os.walk recursion
                    dirs[:] = [d for d in dirs if not is_path_excluded(Path(root).relative_to(self.workspace_path) / d, exclude_names)]

                    for file in files:
                        if file.endswith(('.pyc', '.pyo', '.pyd')):
                            continue
                        
                        full_path = Path(root) / file
                        rel_path = full_path.relative_to(self.workspace_path)
                        if is_path_excluded(rel_path, exclude_names):
                            continue

                        # Skip the zip itself
                        if full_path.resolve() == output_zip_path.resolve():
                            continue

                        # Safe relative path inside the zip
                        rel_path_zip = rel_path
                        # Avoid overwriting our newly generated README.md if they have one
                        if rel_path_zip.name.lower() == "readme.md" and exclude_keys:
                            rel_path_zip = rel_path_zip.with_name("ORIGINAL_README.md")

                        try:
                            zipf.write(str(full_path), str(rel_path_zip))
                        except Exception:
                            pass
                        zipped_count += 1
                        print_progress_bar(100.0 * zipped_count / total_files, "Compressing:")

        import sys
        sys.__stdout__.write("\n")
        sys.__stdout__.flush()

    def _upload_file(self, zip_filepath: Path, expiry_hours: float) -> str:
        # Determine expiry string for server
        if expiry_hours <= 0.25:
            exp = "15m"
        elif expiry_hours <= 1.0:
            exp = "1h"
        elif expiry_hours <= 4.0:
            exp = "4h"
        elif expiry_hours <= 24.0:
            exp = "1d"
        elif expiry_hours <= 72.0:
            exp = "3d"
        else:
            exp = "7d"

        # Check UTIM_SERVER_URL env var, defaulting to production Railway server
        server_url = os.getenv("UTIM_SERVER_URL", "https://api.utim.dev")
        if not server_url:
            raise RuntimeError("No share server URL configured.")

        from utim_cli.config import config
        api_key = config.get("api_key")
        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key

        url = f"{server_url}/shares/upload"
        try:
            with open(zip_filepath, 'rb') as f:
                response = requests.post(url, files={"file": f}, data={"expires": exp}, headers=headers, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("link"):
                    return data["link"]
                else:
                    raise RuntimeError("Server response missing download link.")
            else:
                try:
                    err_msg = response.json().get("detail", response.text)
                except Exception:
                    err_msg = response.text
                raise RuntimeError(err_msg)
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Network error contacting Railway server: {e}")
        except Exception as e:
            raise RuntimeError(f"{e}")
