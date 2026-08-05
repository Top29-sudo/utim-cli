# Privacy Policy
*Last Updated: July 10, 2026*

We value your privacy and are committed to protecting your personal data. This Privacy Policy explains how UTIM ("we," "our," or "us") collects, uses, processes, and safeguards your information when you use our website and related CLI services.

## 1. Information We Collect

We collect information that is necessary to provide, secure, and improve our services.

### 1.1 Account Information

When you sign in or register on our site, we collect:

- Email address (for authentication, billing notifications, and critical communication).
- Display Name and Profile Picture (optional, provided through Google OAuth or email sign-up).
- Firebase User ID (a secure, unique identifier to link your billing and sessions).

### 1.2 Usage Data

To orchestrate your AI sessions and monitor token consumption, we collect:

- Chat conversation history (stored securely on our servers to enable persistent sessions).
- File modification metadata (file paths and git-style diff structure to support undo commands; we do not store full contents).
- Session metrics (execution duration, command status, iteration counts).
- Credit consumption log (tokens consumed per model request for accounting purposes).

### 1.3 What We Do NOT Collect

- **Source Code Files**: Your code snippets, workspace files, and outputs sent to LLM endpoints are processed in-memory. We do not store or train models on your source code.
- **Local Database/Vector Memory**: Any locally indexed vector database memory (e.g., project embeddings) is saved exclusively on your local machine under your user profile directory. We have no access to it.
- **Browsing History**: We do not collect browsing data outside of explicit Playwright browser automation sessions initiated by your prompts.

---

## 2. Local vs. Cloud Data Handling

### 2.1 Data Stored LOCALLY (Your Machine)

The following data resides exclusively on your local machine:

| Data Type | Location | Access |
|-----------|----------|--------|
| Vector embeddings / project memory | `~/.utim/memory/` or project `.utim/` folder | ✅ You only |
| Local config & API key | `~/.utim/config.json` or environment variables | ✅ You only |
| Chat history (local mode) | `~/.utim/chats/` folder | ✅ You only |
| Session state | Temporary files in system temp | ✅ You only |
| MCP tool configurations | `~/.utim/mcp_registry.json` | ✅ You only |

**We have ZERO access to any local data.** It never leaves your machine.

### 2.2 Data Stored in the CLOUD (Our Servers)

| Data Type | Purpose | Retention |
|-----------|---------|-----------|
| Account email & auth tokens | Authentication & account management | Until account deletion |
| Cloud chat history | Sync across devices & sessions | Until you delete or close account |
| Credit/usage logs | Billing & quota tracking | 12 months minimum |
| Subscription status | Access control to paid features | While subscription active |

### 2.3 Data Processed Externally (Third-Party APIs)

When you use LLMs, your prompts may be processed by:

- **OpenRouter / OpenAI / Anthropic / Google**: AI model providers - subject to their privacy policies
- **Tavily**: Web search results - not linked to your account

> **Note**: Prompts sent through OpenRouter follow their zero-retention policies. Check provider docs for latest practices.

---

## 3. How We Use Your Information

We process your data to fulfill our agreement with you and for legitimate business purposes:

- **Service Delivery**: Operating the autonomous planning agent, executing commands, and parsing model outputs.
- **Authentication & Security**: Verifying your identity, protecting against fraudulent access, and preventing credit abuse.
- **Product Improvements**: Reviewing anonymous telemetry (which you can toggle off in settings) to optimize agent reasoning.
- **Billing & Account Management**: Charging subscription plans and deducting top-up credits.

---

## 4. Data Storage and Security

- **Encryption**: All data in transit is encrypted using HTTPS and TLS protocols. Database records are stored securely on Railway servers.
- **Access Control**: We enforce strict per-user database isolation. No user can view or query files, credits, or chat histories belonging to another account.
- **Retention**: Conversation histories are retained until you delete them or close your account. For Hobbyist plans, history is limited to the last 10 sessions.

---

## 5. Third-Party Services

We partner with the following entities to deliver UTIM services:

- **Firebase**: For secure user authentication and account metadata storage.
- **Railway**: For cloud hosting, FastAPI server endpoints, and PostgreSQL database storage.
- **OpenRouter**: To route prompts to various LLMs (Claude, GPT, Gemini, Cohere, etc.). Prompts sent through OpenRouter are subject to their strict zero-retention policies.
- **Tavily**: For internet search functionality inside the browser automation tools.

We do **not** sell, rent, or trade your personal data to third parties.

---

## 6. Your Rights and Choices

Depending on your location, you may have the following rights regarding your data:

- **Access & Portability**: Request a copy of your chat history and account telemetry.
- **Correction**: Edit or update your profile display name or password.
- **Deletion**: Permanently delete your account, which immediately purges all database records, chat logs, and billing logs from our active servers.
- **Telemetry Opt-Out**: You can disable analytical telemetry tracking in the client settings file.

---

## 7. Contact Us

For questions regarding this Privacy Policy or your data, please contact:

- **Email**: support@utim.dev or uthinkimake.official@gmail.com
- **Discord**: Join our community at [Discord Support Channel](https://discord.com/invite/wGB7M8pMEy)