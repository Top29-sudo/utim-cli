import React from 'react';
import { BookOpen, Terminal, Code2, Sparkles, Command, ShieldCheck, Layers } from 'lucide-react';

export default function DocsQuickstartSection() {
  const slashCommands = [
    { cmd: "/login", desc: "Authenticate your terminal with your UTIM account and sync quota." },
    { cmd: "/undo", desc: "Roll back the most recent file modification snapshotted by the agent." },
    { cmd: "/rewind", desc: "Revert conversation state and workspace diffs to an earlier turn." },
    { cmd: "/share", desc: "Zip workspace state and generate a secure collaborative cloud link." },
    { cmd: "/quotashare", desc: "Transfer subscription credits or Quota Bank to a teammate." },
    { cmd: "/redeem", desc: "Claim bonus credits using a distributed promo or redemption code." },
    { cmd: "/mcp", desc: "List, inspect, and connect active Model Context Protocol servers." },
    { cmd: "/help", desc: "Display interactive cheatsheet and active shortcut keybindings." }
  ];

  return (
    <section className="st-docs-section" id="docs">
      <div className="st-container">
        {/* Section Header */}
        <div className="st-section-header">
          <div className="st-hero-badge">
            <BookOpen size={14} /> OPERATING MANUAL & QUICKSTART
          </div>
          <h2 className="st-section-title">
            Terminal CLI Operating Manual
          </h2>
          <p className="st-section-subtitle">
            Everything you need to configure, run, and master UTIM CLI in your daily development workflow.
          </p>
        </div>

        {/* 3-Column Docs Cards */}
        <div className="st-docs-grid">
          {/* Card 1: CLI Entrypoints */}
          <div className="st-doc-card">
            <h3 className="st-doc-card-title">
              <Terminal size={20} /> CLI Entrypoints
            </h3>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: 12 }}>
              Launch interactive TUI or dispatch one-off autonomous tasks:
            </p>
            
            <div className="st-code-block">
              <div># Interactive Full-Screen TUI</div>
              <div style={{ color: '#4ade80' }}>cd my-project && utim</div>
              <br />
              <div># Non-interactive One-Shot Task</div>
              <div style={{ color: '#38bdf8' }}>utim task "Fix failing tests"</div>
              <br />
              <div># Safe Dry-Run (No File Mutations)</div>
              <div style={{ color: '#facc15' }}>utim --dry-run</div>
            </div>
            
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Flags: <code>--dry-run</code>, <code>--sandbox</code>, <code>--version</code>
            </p>
          </div>

          {/* Card 2: Interactive Slash Commands */}
          <div className="st-doc-card">
            <h3 className="st-doc-card-title">
              <Command size={20} /> Interactive Slash Commands
            </h3>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: 12 }}>
              Execute powerful system actions directly inside the terminal session:
            </p>

            <table className="st-commands-table">
              <tbody>
                {slashCommands.map((item, idx) => (
                  <tr key={idx}>
                    <td className="st-cmd-name">{item.cmd}</td>
                    <td style={{ color: 'var(--text-secondary)' }}>{item.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Card 3: Architecture & Security */}
          <div className="st-doc-card">
            <h3 className="st-doc-card-title">
              <ShieldCheck size={20} /> Local-First Architecture
            </h3>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: 12 }}>
              UTIM operates locally inside your folder, bootstrapping <code>.utim/</code> on startup:
            </p>

            <ul style={{ listStyle: 'none', fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
              <li>✔ <strong>Workspace Intelligence:</strong> SQLite database in <code>.utim/</code>.</li>
              <li>✔ <strong>Semantic RAG:</strong> ChromaDB vector embeddings.</li>
              <li>✔ <strong>Custom Rules:</strong> Auto-loads <code>AGENTS.md</code> & <code>SKILL.md</code>.</li>
              <li>✔ <strong>MCP Protocols:</strong> Stdio & SSE tool-calling connections.</li>
              <li>✔ <strong>Safety Sandbox:</strong> User confirmations for shell commands.</li>
            </ul>

            <div className="st-code-block" style={{ marginTop: 16 }}>
              <div># Optional full feature bundle</div>
              <div style={{ color: '#4ade80' }}>pip install ".[full]"</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
