# UTIM Compatibility Guide

Detailed compatibility information for UTIM installations.

---

## Python Compatibility

| Python Version | Status | Notes |
|----------------|--------|-------|
| 3.10 | ✅ Supported | Minimum required |
| 3.11 | ✅ Supported | Recommended |
| 3.12 | ✅ Supported | Full support |
| 3.13 | ✅ Supported | Latest features |
| < 3.10 | ❌ Not Supported | Use pyenv or virtualenv |

### Required Python Dependencies

```
asyncio
fire
rich
prompt_toolkit>=3.0.38
pyyaml
requests
chromadb>=0.4.22
numpy
playwright
anthropic
openai
google-generativeai
aiohttp
```

---

## Operating System Support

### Windows

| Version | Status | Notes |
|---------|--------|-------|
| Windows 10 (1903+) | ✅ Supported | Minimum |
| Windows 11 | ✅ Supported | Recommended |
| Windows Server 2019+ | ✅ Supported | Server environments |

**Requirements:**
- PowerShell 5.1+ or Windows Terminal
- Visual C++ Build Tools (for some packages)

### macOS

| Version | Status | Notes |
|---------|--------|-------|
| 11 (Big Sur) | ✅ Supported | Minimum |
| 12+ | ✅ Supported | Full support |
| 14 (Sonoma) | ✅ Supported | Recommended |

**Requirements:**
- Terminal.app, iTerm2, or Hyper
- Command Line Tools (`xcode-select --install`)

### Linux

| Distribution | Status | Notes |
|--------------|--------|-------|
| Ubuntu 20.04+ | ✅ Supported | Minimum |
| Debian 11+ | ✅ Supported | |
| Fedora 36+ | ✅ Supported | |
| Arch Linux | ✅ Supported | |
| RHEL 9+ | ✅ Supported | |

**Requirements:**
- bash 4.0+
- glibc 2.31+
- libstdc++

---

## Terminal Compatibility

| Terminal | Version | Features |
|----------|---------|----------|
| Windows Terminal | 1.0+ | Full TUI support |
| iTerm2 | 3.4+ | Full support |
| Terminal.app | Latest | Full support |
| VS Code Terminal | 1.70+ | Full support |
| Hyper | 3.0+ | Full support |
| Alacritty | 0.10+ | Full support |
| cmd.exe | - | Limited (no TUI colors) |
| PowerShell | 5.1+ | Full support |
| bash (Linux/macOS) | 4.0+ | Full support |
| zsh | 5.0+ | Full support |

---

## LLM Provider Compatibility

| Provider | API Version | Auth Method | Status |
|----------|-------------|-------------|--------|
| OpenRouter | v1 | API Key | ✅ |
| OpenAI | v1 | API Key | ✅ |
| Anthropic | 2023-06-01 | API Key | ✅ |
| Google AI (Gemini) | v1beta | API Key | ✅ |
| Azure OpenAI | 2024-02-01 | API Key + Endpoint | ✅ |
| Ollama | v1 | Local | ✅ |
| Cohere | v1 | API Key | ✅ |
| Together AI | v1 | API Key | ✅ |

---

## MCP Server Compatibility

UTIM supports MCP (Model Context Protocol) servers. Compatible servers include:

- Filesystem MCP
- GitHub MCP
- Slack MCP
- Puppeteer/Browser MCP
- PostgreSQL MCP
- Custom MCP servers (OpenAI-compatible)

---

## Browser Automation (Playwright)

| Browser | Minimum Version | Notes |
|---------|-----------------|-------|
| Chrome/Chromium | 90+ | Default |
| Firefox | 90+ | Supported |
| WebKit | 15+ | macOS only |

---

## Installation Methods

### pip (Recommended)

```bash
pip install .
pip install ".[full]"  # With all optional dependencies
```

### Development Install

```bash
pip install -e .
pip install -e ".[dev,full]"
```

### Docker

```bash
docker run -it utimcli/utim --help
```

---

## Known Limitations

| Feature | Limitation |
|---------|------------|
| TUI Colors | 256-color terminal required |
| Sandbox Mode | Linux/WSL only (not full support on Windows) |
| Vector Memory | Requires 500MB+ disk space |
| Playwright | Chromium download required (~150MB) |

---

## Troubleshooting Compatibility

### Python Version Issues

```bash
# Check your Python version
python --version

# Use pyenv to manage versions
pyenv install 3.11
pyenv local 3.11
```

### Terminal Issues

If colors don't display correctly:
```bash
# Check terminal capabilities
echo $TERM
# Should be xterm-256color or screen-256color
```

### Windows-Specific

If you encounter installation errors:
1. Install Visual C++ Build Tools
2. Use Python 3.11+ from python.org or Microsoft Store

---

*Last updated: July 2026*