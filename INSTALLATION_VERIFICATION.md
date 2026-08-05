# Installation Verification Guide

This guide helps verify that UTIM is correctly installed and configured.

---

## Quick Verification (30 seconds)

Run these commands to verify your installation:

```bash
# 1. Check utim is installed
utim --version

# 2. Check doctor output
utim doctor

# 3. Try starting (will prompt for config if not set up)
utim --help
```

If all three commands work, your installation is successful.

---

## Detailed Verification Steps

### 1. Python Version Check

```bash
python --version
# Should show Python 3.10 or higher
```

### 2. Package Installation Check

```bash
# Check pip installed version
pip show utim-cli

# Or check import directly
python -c "import utim_cli; print(utim_cli.__version__)"
```

### 3. Command Availability

```bash
# Verify command is in PATH
which utim   # Linux/macOS
where utim   # Windows

# Or try running it
utim --help
```

### 4. Dependencies Check

```bash
# Run doctor command
utim doctor
```

Expected output should show:
- ✅ Python version (3.10+)
- ✅ Required packages installed
- ✅ Network connectivity (optional)
- ✅ API configuration status

### 5. First-Time Setup

```bash
utim init
```

This creates:
- `~/.utim/config.json` - Configuration file
- `~/.utim/memory/` - Vector database directory

---

## Troubleshooting

### "Command not found" Error

**Problem**: `utim` command not found after installation.

**Solution**:
```bash
# Reinstall with proper PATH
pip uninstall utim-cli
pip install -e .  # Development install

# Or add to PATH manually
export PATH="$PATH:$HOME/.local/bin"  # Linux
# Restart your terminal
```

### Version Mismatch

**Problem**: Running old version after upgrade.

**Solution**:
```bash
# Force reinstall
pip install --force-reinstall utim-cli
```

### Import Errors

**Problem**: `ModuleNotFoundError` when running.

**Solution**:
```bash
# Check installed packages
pip list | grep -i utim

# Reinstall dependencies
pip install -r requirements.txt
```

### Permission Errors

**Problem**: Cannot write to config directory.

**Solution**:
```bash
# Linux/macOS
chmod -R 755 ~/.utim
# Or delete and recreate
rm -rf ~/.utim
utim init
```

---

## Test Your Installation

### Automated Test

Run the E2E tests:

```bash
# Run all tests
pytest tests/test_e2e.py -v

# Run quick tests only
pytest tests/test_e2e.py -v -m "not slow"
```

### Manual Test

1. Run `utim --version` - Should show version
2. Run `utim doctor` - Should show diagnostics
3. Run `utim task "say hello"` - Should attempt to run (may fail if no API key)

---

## Verify Update

After updating UTIM:

```bash
# Check new version
utim --version

# Verify doctor still works
utim doctor

# Check changelog
cat CHANGELOG.md | head -50
```

---

## Getting Help

If verification fails:

1. **Check Discord**: discord.com/invite/wGB7M8pMEy
2. **Run diagnostics**: `utim doctor` and save output
3. **Generate report**: In chat, type `/report`
4. **Email**: support@utim.dev

---

*Last updated: July 2026*