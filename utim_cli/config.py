import json
import logging
import os
import pathlib
import shutil
import time
import hashlib
import hmac
from typing import Any, Dict, Optional

logger = logging.getLogger("utim.config")


# ── CLI install identity & request signing ───────────────────────────────────
# Used by client_utils.py to attach X-UTIM-* headers to every server-bound
# request and (when the server enforces signing) to compute X-UTIM-CLI-Signature.
# The server defines the canonical string in utim_cli/server/cli_auth.py.

_INSTALL_ID: str = ""
_HMAC_SECRET: bytes = b""               # populated lazily from environment / config
_LAST_CHALLENGE_FETCH: float = 0.0
_CHALLENGE_CACHE: dict = {"nonce": "", "expires_at": 0}


def _load_install_id() -> str:
    """Read or generate the persistent install ID (uuid4 stored on disk)."""
    global _INSTALL_ID
    if _INSTALL_ID:
        return _INSTALL_ID
    try:
        uid_path = get_utim_dir() / "install_id"
        if uid_path.exists():
            _INSTALL_ID = uid_path.read_text(encoding="utf-8").strip() or _generate_install_id()
        else:
            _INSTALL_ID = _generate_install_id()
            uid_path.parent.mkdir(parents=True, exist_ok=True)
            uid_path.write_text(_INSTALL_ID, encoding="utf-8")
    except Exception:
        _INSTALL_ID = _generate_install_id()
    return _INSTALL_ID


def _generate_install_id() -> str:
    import uuid
    return f"inst-{uuid.uuid4().hex}"


def get_install_id() -> str:
    """Public accessor — returns the per-install UUID."""
    return _load_install_id()


def get_cli_version() -> str:
    try:
        from utim_cli._version import VERSION  # type: ignore
        return VERSION
    except Exception:
        return "unknown"


def get_hmac_secret() -> bytes:
    """Return the build-embedded HMAC secret used to sign requests.

    Source priority:
      1. UTIM_CLI_HMAC_SECRET environment variable (dev / override)
      2. Persisted config value (set by the CLI on first launch from a baked-in default)
      3. A stable derived default — sufficient for the server to log but NOT to
         authenticate (server treats unknown secrets as "unsigned legacy client")
    """
    global _HMAC_SECRET
    if _HMAC_SECRET:
        return _HMAC_SECRET
    env_secret = os.environ.get("UTIM_CLI_HMAC_SECRET", "").strip()
    if env_secret:
        _HMAC_SECRET = env_secret.encode("utf-8")
        return _HMAC_SECRET
    try:
        stored = config.get("cli_hmac_secret")
        if stored:
            _HMAC_SECRET = stored.encode("utf-8")
            return _HMAC_SECRET
    except Exception:
        pass
    # Stable fallback derived from install_id — server rejects but client code
    # still works without raising. The server logs these as "unsigned legacy".
    _HMAC_SECRET = hashlib.sha256(("utim-legacy:" + get_install_id()).encode("utf-8")).digest()
    return _HMAC_SECRET


def _fetch_challenge(server_url: str) -> dict:
    """Ask the server for a fresh nonce. Cached for 30s to avoid spamming."""
    global _LAST_CHALLENGE_FETCH, _CHALLENGE_CACHE
    now = time.time()
    if _CHALLENGE_CACHE.get("nonce") and _CHALLENGE_CACHE.get("expires_at", 0) > now + 5:
        if (now - _LAST_CHALLENGE_FETCH) < 30:
            return _CHALLENGE_CACHE
    try:
        import requests as _req
        r = _req.get(
            f"{server_url.rstrip('/')}/auth/cli-challenge",
            headers={
                "X-UTIM-Install-ID": get_install_id(),
                "User-Agent": f"UTIM-CLI/{get_cli_version()} (+https://utim.dev)",
            },
            timeout=5,
        )
        if r.status_code == 200:
            data = r.json()
            _CHALLENGE_CACHE = {
                "nonce": data.get("nonce", ""),
                "expires_at": int(data.get("expires_at", 0)),
                "enforcement_enabled": bool(data.get("enforcement_enabled", False)),
            }
            _LAST_CHALLENGE_FETCH = now
    except Exception:
        pass
    return _CHALLENGE_CACHE


def sign_request_for_server(method: str, path: str, body: Any) -> dict:
    """Build the X-UTIM-* signature headers for a server-bound request.

    Returns {} silently if signing is not available (no network, no secret).
    """
    try:
        from utim_cli.client_utils import get_server_url
        server_url = get_server_url()
    except Exception:
        return {}

    challenge = _fetch_challenge(server_url)
    nonce = (challenge or {}).get("nonce") or ""
    if not nonce:
        return {}

    if body is None:
        body_bytes = b""
    elif isinstance(body, (bytes, bytearray)):
        body_bytes = bytes(body)
    else:
        try:
            body_bytes = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
        except Exception:
            body_bytes = str(body).encode("utf-8")

    body_hash = hashlib.sha256(body_bytes).hexdigest()
    install_id = get_install_id()
    canonical = f"{method.upper()}\n{path}\n{nonce}\n{install_id}\n{body_hash}"

    secret = get_hmac_secret()
    signature = hmac.new(secret, canonical.encode("utf-8"), hashlib.sha256).hexdigest()

    return {
        "X-UTIM-Nonce": nonce,
        "X-UTIM-CLI-Signature": signature,
        "X-UTIM-CLI-Version": get_cli_version(),
        "X-UTIM-Install-ID": install_id,
    }

# ── SSL session patch ─────────────────────────────────────────────────────────
# Keeps a reference to the true original so toggling works correctly in both
# directions without chaining patches on top of each other.
_ORIGINAL_SESSION_REQUEST = None
_SSL_PATCH_ACTIVE = False

def _apply_ssl_session_patch(disable: bool) -> None:
    """Apply or remove the verify=False monkey-patch on requests.Session.request.

    Safe to call multiple times. Does nothing when the requested state already
    matches the current state.
    """
    global _ORIGINAL_SESSION_REQUEST, _SSL_PATCH_ACTIVE
    try:
        import requests as _req_mod
        import urllib3

        # Capture the true original exactly once.
        if _ORIGINAL_SESSION_REQUEST is None:
            _ORIGINAL_SESSION_REQUEST = _req_mod.Session.request

        if disable and not _SSL_PATCH_ACTIVE:
            # Suppress noisy InsecureRequestWarning lines.
            try:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except Exception:
                pass
            _orig = _ORIGINAL_SESSION_REQUEST
            def _ssl_off(self, method, url, *args, **kwargs):
                kwargs.setdefault('verify', False)
                return _orig(self, method, url, *args, **kwargs)
            _req_mod.Session.request = _ssl_off
            _SSL_PATCH_ACTIVE = True

        elif not disable and _SSL_PATCH_ACTIVE:
            # Restore the true original so verify defaults to True again.
            _req_mod.Session.request = _ORIGINAL_SESSION_REQUEST
            _SSL_PATCH_ACTIVE = False

    except Exception:
        pass

def get_utim_dir() -> pathlib.Path:
    """Return the centralized .utim directory path.
    If running within a pytest environment, uses the current directory's .utim folder
    to isolate test side-effects. Otherwise, resolves to the user's home directory.
    """
    import sys
    if "pytest" in sys.argv[0] or "py.test" in sys.argv[0] or "PYTEST_CURRENT_TEST" in os.environ:
        return pathlib.Path('.utim')
    return pathlib.Path.home() / ".utim"


class Config:
    def __init__(self):
        import sys
        if "pytest" in sys.argv[0] or "py.test" in sys.argv[0] or "PYTEST_CURRENT_TEST" in os.environ:
            import tempfile
            # Use a static attribute or global reference if needed to keep the temp dir alive
            self._temp_dir_holder = tempfile.TemporaryDirectory()
            self.global_dir = pathlib.Path(self._temp_dir_holder.name) / ".utim"
            self.local_dir = pathlib.Path(self._temp_dir_holder.name) / ".utim"
        else:
            self.global_dir = get_utim_dir()
            self.local_dir = get_utim_dir()
        self._global_data: Dict[str, Any] = {}
        self._local_data: Dict[str, Any] = {}
        self._load()
        # Always inject a browser User-Agent to prevent firewalls/proxies blocking default python-requests.
        # We patch Session.request (not __init__) so it applies to ALL sessions regardless of when
        # they were created, and even when callers pass their own headers dict (the UA is merged in
        # without overwriting any caller-supplied headers that may already have a User-Agent set).
        try:
            import requests as _req_mod
            _BROWSER_UA = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
            _original_request = _req_mod.Session.request
            config_instance = self

            def _ua_patched_request(self, method, url, *args, **kwargs):
                # Merge headers so we never overwrite a caller-supplied User-Agent
                hdrs = kwargs.pop("headers", None) or {}
                if isinstance(hdrs, dict):
                    hdrs = dict(hdrs)
                else:
                    hdrs = dict(hdrs)
                hdrs.setdefault("User-Agent", _BROWSER_UA)
                
                # Append user's preferred quota preference to headers
                pref = config_instance.get("preferred_quota", "regular")
                hdrs.setdefault("X-Preferred-Quota", pref)
                
                kwargs["headers"] = hdrs

                primary_host = "api.utim.dev"
                fallback_host = "utim-cli-production.up.railway.app"

                if primary_host in url:
                    try:
                        return _original_request(self, method, url, *args, **kwargs)
                    except _req_mod.exceptions.RequestException as e:
                        fallback_url = url.replace(primary_host, fallback_host)
                        return _original_request(self, method, fallback_url, *args, **kwargs)
                elif fallback_host in url:
                    try:
                        return _original_request(self, method, url, *args, **kwargs)
                    except _req_mod.exceptions.RequestException as e:
                        fallback_url = url.replace(fallback_host, primary_host)
                        return _original_request(self, method, fallback_url, *args, **kwargs)

                return _original_request(self, method, url, *args, **kwargs)

            _req_mod.Session.request = _ua_patched_request
        except Exception:
            pass

        # Apply SSL patch immediately if already disabled in config.
        _apply_ssl_session_patch(disable=not self.verify_ssl)

    def _load(self):
        # Load global config
        global_config = self.global_dir / "config.json"
        if global_config.exists():
            try:
                with open(global_config, "r", encoding="utf-8") as f:
                    self._global_data = json.load(f)
            except json.JSONDecodeError as e:
                logger.warning(f"Global config corrupted at {global_config}: {e}. Using defaults.")
            except Exception as e:
                logger.error(f"Cannot read global config: {e}")
        
        # Load local config if exists and is different from global config path
        local_config = self.local_dir / "config.json"
        if local_config.exists():
            try:
                if local_config.resolve() != global_config.resolve():
                    with open(local_config, "r", encoding="utf-8") as f:
                        self._local_data = json.load(f)
            except Exception as e:
                logger.error(f"Cannot read local config: {e}")

    @property
    def _data(self) -> Dict[str, Any]:
        """Returns a merged view (local overrides global)."""
        merged = dict(self._global_data)
        merged.update(self._local_data)
        return merged

    def save(self):
        # Save to global config directory
        self.global_dir.mkdir(parents=True, exist_ok=True)
        global_config = self.global_dir / "config.json"
        try:
            with open(global_config, "w", encoding="utf-8") as f:
                json.dump(self._global_data, f, indent=4)
        except Exception as e:
            logger.error(f"Cannot write global config: {e}")

        # Save to local config directory if we have local data and it's a different path
        local_config = self.local_dir / "config.json"
        try:
            if self._local_data and local_config.resolve() != global_config.resolve():
                self.local_dir.mkdir(parents=True, exist_ok=True)
                with open(local_config, "w", encoding="utf-8") as f:
                    json.dump(self._local_data, f, indent=4)
        except Exception as e:
            logger.error(f"Cannot write local config: {e}")

    def reload(self):
        """Reload configuration data from disk."""
        self._global_data = {}
        self._local_data = {}
        self._load()

    def get(self, key: str, default: Any = None) -> Any:
        if key == "disabled_tools" and "disabled_tools" not in self._data:
            return ["generate_3d_model"]
        val = self._data.get(key, default)
        if val is None:
            if key == "api_key":
                return os.getenv("UTIM_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
            elif key == "email":
                return os.getenv("UTIM_EMAIL")
        return val

    def set(self, key: str, value: Any, local: bool = False):
        if local:
            self._local_data[key] = value
        else:
            if key in self._local_data:
                self._local_data[key] = value
            self._global_data[key] = value
        self.save()

    @property
    def token(self) -> Optional[str]:
        return self.get("token")

    @property
    def email(self) -> str:
        if not self.get("api_key"):
            return "GUEST"
        return self.get("email", os.getenv("UTIM_EMAIL", "GUEST"))

    @property
    def name(self) -> Optional[str]:
        return self.get("name")

    def clear(self):
        # Clear only user credentials, keep preferences and custom models
        auth_keys = ["token", "email", "uid", "name", "api_key", "user_plan"]
        for key in auth_keys:
            self._global_data.pop(key, None)
            self._local_data.pop(key, None)
        self.save()

    # ── Custom / Bring-Your-Own-Model support ─────────────────────────────────

    @property
    def custom_models(self) -> list:
        """Return the list of user-defined models.

        Each entry is a dict with the following keys:
          model_id      – unique identifier shown in the picker (e.g. "gpt-4o")
          provider_name – human-readable label (e.g. "OpenAI")
          base_url      – OpenAI-compatible chat completions base URL
                         (e.g. "https://api.openai.com/v1")
          api_key       – API key for that provider (stored in plain text
                          in .utim/config.json; the user is warned)
          context_window – integer token budget (default 128 000)
        """
        return self._data.get("custom_models", [])

    @custom_models.setter
    def custom_models(self, value: list):
        self.set("custom_models", value)

    def add_custom_model(self, entry: dict) -> None:
        """Append or replace a custom model entry keyed on model_id."""
        models = self.custom_models
        models = [m for m in models if m.get("model_id") != entry["model_id"]]
        
        api_key = entry.get("api_key")
        use_keyring = False
        if api_key:
            try:
                import keyring
                keyring.set_password("utim_cli", entry["model_id"], api_key)
                use_keyring = True
            except Exception as e:
                logger.warning(f"Keyring not available, storing key in plain text: {e}")
                
        entry_to_save = dict(entry)
        if use_keyring:
            entry_to_save.pop("api_key", None)
            
        models.append(entry_to_save)
        self.custom_models = models

    def remove_custom_model(self, model_id: str) -> bool:
        """Remove a custom model by model_id. Returns True if it existed."""
        models = self.custom_models
        new = [m for m in models if m.get("model_id") != model_id]
        if len(new) == len(models):
            return False
            
        try:
            import keyring
            keyring.delete_password("utim_cli", model_id)
        except Exception:
            pass
            
        self.custom_models = new
        return True

    def remove_custom_provider(self, provider_name: str, base_url: str) -> int:
        """Remove all custom models associated with a provider. Returns count removed."""
        models = self.custom_models
        new = []
        removed = 0
        try:
            import keyring
            has_keyring = True
        except ImportError:
            has_keyring = False
            
        for m in models:
            if m.get("provider_name") == provider_name and m.get("base_url") == base_url:
                removed += 1
                if has_keyring:
                    try:
                        keyring.delete_password("utim_cli", m["model_id"])
                    except Exception:
                        pass
            else:
                new.append(m)
                
        if removed > 0:
            self.custom_models = new
        return removed

    def get_custom_model(self, model_id: str) -> Optional[dict]:
        """Return the custom model entry for *model_id*, or None."""
        for m in self.custom_models:
            if m.get("model_id") == model_id:
                m_ret = dict(m)
                try:
                    import keyring
                    key = keyring.get_password("utim_cli", model_id)
                    if key:
                        m_ret["api_key"] = key
                except Exception:
                    pass
                return m_ret
        return None

    @property
    def debug_mode(self) -> bool:
        return os.environ.get("UTIM_DEBUG", "0").lower() in ("1", "true", "yes")

    @property
    def dry_run(self) -> bool:
        return os.environ.get("UTIM_DRY_RUN", "0").lower() in ("1", "true", "yes") or self.get("dry_run", False)


    @property
    def fallback_models(self) -> list:
        """Return fallback LLM models list."""
        models = os.environ.get("UTIM_FALLBACK_MODELS")
        if models:
            return [m.strip() for m in models.split(",")]
        return [
            "cohere/north-mini-code:free",
            "openrouter/free",
            "inclusionai/ling-3.0-flash:free",
        ]


    @property
    def keep_full_turns(self) -> int:
        # Number of recent turns to retain in memory

        try:
            return int(os.environ.get("UTIM_KEEP_TURNS", "10"))
        except ValueError:
            return 10

    @property
    def compression_enabled(self) -> bool:
        # Enable adaptive context compression
        return os.environ.get("UTIM_COMPRESSION", "true").lower() in ("1", "true", "yes")

    @property
    def verify_ssl(self) -> bool:
        env_val = os.environ.get("UTIM_VERIFY_SSL")
        if env_val is not None:
            return env_val.lower() not in ("false", "0", "no")
        return self.get("verify_ssl", True)

    @property
    def blender_path(self) -> str:
        """Return the absolute path to the Blender executable.

        Detection order:
        1. Environment variable ``UTIM_BLENDER_PATH``
        2. Stored user config key ``blender_path``
        3. Common Windows install locations
        4. ``shutil.which('blender')`` fallback
        """
        # 1. explicit env var
        env_path = os.getenv("UTIM_BLENDER_PATH")
        if env_path and os.path.isfile(env_path):
            return env_path
        # 2. stored in config file
        stored = self.get("blender_path")
        if stored and os.path.isfile(stored):
            return stored
        # 3. common install locations (Windows default)
        common_paths = [
            r"C:\\Program Files\\Blender Foundation\\Blender\\blender.exe",
            r"C:\\Program Files (x86)\\Blender Foundation\\Blender\\blender.exe",
            r"E:\\Blender\\blender.exe",
        ]
        for p in common_paths:
            if os.path.isfile(p):
                return p
        # 4. which search (covers custom PATH entries)
        which_path = shutil.which("blender")
        if which_path:
            return which_path
        # Fallback – raise informative error later when used
        return ""

# Global config instance
config = Config()
# Convenience constant for direct access
BLENDER_PATH = config.blender_path
