import React, { useState } from 'react';
import SEOHead from '../components/SEOHead';
import ScrollytellingHeaderNav from '../components/ScrollytellingHeaderNav';
import ScrollytellingFooter from '../components/ScrollytellingFooter';
import { 
  Terminal, Shield, Package, Command, ExternalLink, Copy, Check, Sparkles, 
  Bot, Cpu, Database, RotateCcw, Layers, DollarSign, Gift, Lock, RefreshCw, 
  HelpCircle, Scale, FileCode, CheckCircle2, ChevronRight
} from 'lucide-react';
import './DocsPage.css';

export default function DocsPage() {
  const [copiedId, setCopiedId] = useState(null);

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="docs-main-page">
      <SEOHead
        title="UTIM CLI Complete Documentation — Operating Manual"
        description="This page is the complete operating manual for UTIM CLI, the local-first autonomous developer agent for terminal-based software engineering."
        canonical="https://utim.dev/docs"
      />

      {/* Top Header Navigation matching Screenshot */}
      <ScrollytellingHeaderNav activeSection="documentation" />

      {/* Hero Header Section */}
      <section className="docs-hero-section">
        <div className="docs-eyebrow">
          <span>— 📖 COMPLETE OPERATING MANUAL —</span>
        </div>
        <h1 className="docs-hero-title">UTIM CLI Complete Documentation</h1>
        <p className="docs-hero-desc">
          This page is the complete operating manual for UTIM CLI, the local-first autonomous developer agent for terminal-based software engineering.
        </p>

        {/* Link Banner to Standalone docs.utim.dev Portal */}
        <div className="docs-portal-link-banner">
          <div>
            <strong>Looking for the dedicated interactive docs website?</strong>
            <span>Access docs.utim.dev for live search, copy buttons, and deep API specs.</span>
          </div>
          <a href="https://docs.utim.dev" target="_blank" rel="noreferrer" className="docs-portal-btn">
            Open docs.utim.dev <ExternalLink size={14} />
          </a>
        </div>
      </section>

      {/* Main Cards Layout Container */}
      <div className="docs-cards-container">
        
        {/* ROW 1: TOP 3 CARDS matching Screenshot 2026-08-09 221608 */}
        <div className="docs-grid-3col">
          
          {/* Card 1: What UTIM CLI Is */}
          <div className="docs-card">
            <h2 className="docs-card-title">
              <span className="docs-card-icon">&gt;_</span>
              What UTIM CLI Is
            </h2>
            <p className="docs-card-p">
              UTIM stands for <em>"You Think It, I Make It."</em> It is designed to run inside a project folder, understand the workspace, plan changes, edit files, run local commands, validate results, and keep a reversible record of the work.
            </p>
            <ul className="docs-checklist">
              <li><span className="check">✓</span> Read, inspect, and summarize an entire codebase.</li>
              <li><span className="check">✓</span> Write files and patch existing files safely.</li>
              <li><span className="check">✓</span> Run shell commands with confirmation &amp; sandbox controls.</li>
              <li><span className="check">✓</span> Validate Python, JSON, JS, and TS edits before writing.</li>
              <li><span className="check">✓</span> Maintain undo, redo, and rewind history for agent changes.</li>
              <li><span className="check">✓</span> Persist conversation state &amp; intelligence in <code>.utim/</code>.</li>
            </ul>
          </div>

          {/* Card 2: Installation Methods */}
          <div className="docs-card">
            <h2 className="docs-card-title">
              <Package size={20} className="docs-card-icon" />
              Installation Methods
            </h2>
            <p className="docs-card-p">The primary global install path is via npm:</p>
            
            <div className="docs-terminal-snippet">
              <span className="docs-terminal-prompt">$</span>
              <span style={{ color: '#4ADE80' }}>npm install -g @emend-ai/utim</span>
            </div>

            <p className="docs-card-p" style={{ marginTop: 16 }}>
              Or install with Python pip (requires Python &gt;= 3.9):
            </p>

            <div className="docs-terminal-snippet">
              <span className="docs-terminal-prompt">$</span>pip install utim<br />
              <span className="docs-terminal-comment"># For full optional feature set (search, images, parsers):</span><br />
              <span className="docs-terminal-prompt">$</span><span style={{ color: '#4ADE80' }}>pip install ".[full]"</span>
            </div>
          </div>

          {/* Card 3: First Run & Authentication */}
          <div className="docs-card">
            <h2 className="docs-card-title">
              <Shield size={20} className="docs-card-icon" />
              First Run &amp; Authentication
            </h2>
            <p className="docs-card-p">Start UTIM inside any project repository:</p>

            <div className="docs-terminal-snippet">
              <span className="docs-terminal-prompt">$</span>cd my-project<br />
              <span className="docs-terminal-prompt">$</span><span style={{ color: '#4ADE80' }}>utim</span>
            </div>

            <p className="docs-card-p" style={{ marginTop: 16 }}>
              Authenticate before dispatching cloud prompts:
            </p>

            <div className="docs-terminal-snippet">
              <span className="docs-terminal-prompt">$</span>utim login<br />
              <span className="docs-terminal-comment"># Inside TUI: type /login</span>
            </div>
          </div>

        </div>

        {/* ROW 2: COMMAND LINE ENTRYPOINTS & SLASH COMMANDS */}
        <div className="docs-grid-2col">
          
          {/* Card 4: Command Line Entrypoints */}
          <div className="docs-card">
            <h2 className="docs-card-title">
              <FileCode size={20} className="docs-card-icon" />
              Command Line Entrypoints &amp; Execution Modes
            </h2>
            <p className="docs-card-p">
              Launch interactive TUI mode or autonomous headless task execution:
            </p>
            <div className="docs-terminal-snippet">
              <span className="docs-terminal-comment"># Interactive TUI mode</span><br />
              <span className="docs-terminal-prompt">$</span>utim<br /><br />
              <span className="docs-terminal-comment"># Headless task execution mode</span><br />
              <span className="docs-terminal-prompt">$</span>utim task "Fix failing unit tests" --dry-run
            </div>
            
            <p className="docs-card-p" style={{ marginTop: 16 }}>
              <strong>Execution Flags:</strong> <code>--dry-run</code> (simulates edits), <code>--sandbox</code> (Docker container isolation), <code>--debug</code> (verbose log traces), <code>--version</code> (prints binary version metadata).
            </p>
          </div>

          {/* Card 5: Slash Commands Reference Matrix */}
          <div className="docs-card">
            <h2 className="docs-card-title">
              <Command size={20} className="docs-card-icon" />
              Slash Commands Reference (25+ Commands)
            </h2>
            <p className="docs-card-p">
              Type forward slash (/) inside the prompt to control model routing, rewind edits, or claim credits:
            </p>

            <table className="docs-card-table">
              <thead>
                <tr>
                  <th>Command</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code style={{ color: '#0284C7', fontWeight: 700 }}>/login</code></td>
                  <td>Authenticates CLI and syncs 5-hour quota slot.</td>
                </tr>
                <tr>
                  <td><code style={{ color: '#0284C7', fontWeight: 700 }}>/undo</code></td>
                  <td>Reverts the last turn file edit.</td>
                </tr>
                <tr>
                  <td><code style={{ color: '#0284C7', fontWeight: 700 }}>/rewind</code></td>
                  <td>Restores history and disk diffs to an earlier turn.</td>
                </tr>
                <tr>
                  <td><code style={{ color: '#0284C7', fontWeight: 700 }}>/redeem</code></td>
                  <td>Claims credit bonuses with promo codes.</td>
                </tr>
                <tr>
                  <td><code style={{ color: '#0284C7', fontWeight: 700 }}>/byok</code></td>
                  <td>Configures custom API keys (OpenAI, Anthropic, Ollama).</td>
                </tr>
              </tbody>
            </table>
          </div>

        </div>

        {/* ROW 3: SUBAGENTS, MCP, VECTOR MEMORY */}
        <div className="docs-grid-3col">
          
          {/* Card 6: Subagent Swarm Engine */}
          <div className="docs-card">
            <h2 className="docs-card-title">
              <Bot size={20} className="docs-card-icon" />
              Subagent Swarm Engine
            </h2>
            <p className="docs-card-p">
              Spawns background subagents for parallel research, planning, and task execution without cluttering main agent context:
            </p>
            <ul className="docs-checklist">
              <li><span className="check">✓</span> <strong>research</strong>: Read-only codebase survey &amp; web search.</li>
              <li><span className="check">✓</span> <strong>self</strong>: Full parent capability agent clone.</li>
              <li><span className="check">✓</span> <strong>define_subagent</strong>: Dynamic custom subagent registration.</li>
            </ul>
          </div>

          {/* Card 7: Model Context Protocol (MCP) */}
          <div className="docs-card">
            <h2 className="docs-card-title">
              <Cpu size={20} className="docs-card-icon" />
              Model Context Protocol (MCP)
            </h2>
            <p className="docs-card-p">
              Connect external databases, desktop tools, and browser automation drivers via Stdio &amp; SSE transport streams configured in <code>.agents/mcp_config.json</code>.
            </p>
            <div className="docs-terminal-snippet">
              <span className="docs-terminal-comment"># .agents/mcp_config.json</span><br />
              &#123; "mcpServers": &#123; "sqlite": &#123; "command": "npx" &#125;&#125;&#125;
            </div>
          </div>

          {/* Card 8: Local Vector Memory & ChromaDB */}
          <div className="docs-card">
            <h2 className="docs-card-title">
              <Database size={20} className="docs-card-icon" />
              Vector Memory &amp; ChromaDB RAG
            </h2>
            <p className="docs-card-p">
              Sentence Transformers embeddings stored in local ChromaDB at <code>.utim/chroma/</code>. Provides sub-10ms similarity search and Tree-Sitter AST code chunking.
            </p>
          </div>

        </div>

        {/* ROW 4: LEGAL EULA, BYOK & TROUBLESHOOTING */}
        <div className="docs-grid-2col">
          
          {/* Card 9: Emend AI Proprietary EULA */}
          <div className="docs-card">
            <h2 className="docs-card-title">
              <Scale size={20} className="docs-card-icon" />
              Emend AI Proprietary EULA (Non-MIT)
            </h2>
            <p className="docs-card-p">
              UTIM CLI is <strong>proprietary software owned exclusively by Emend AI</strong>. It is NOT licensed under the MIT License.
            </p>
            <ul className="docs-checklist">
              <li><span className="check">✓</span> <strong>Free Tier:</strong> Personal learning &amp; open-source evaluation only.</li>
              <li><span className="check">✓</span> <strong>Paid Tiers / BYOK:</strong> Required for commercial software development.</li>
            </ul>
          </div>

          {/* Card 10: Diagnostics & Troubleshooting */}
          <div className="docs-card">
            <h2 className="docs-card-title">
              <HelpCircle size={20} className="docs-card-icon" />
              Troubleshooting &amp; Diagnostics
            </h2>
            <p className="docs-card-p">
              Run automated 15-point diagnostic checks or fix UTF-8 character encoding on Windows:
            </p>
            <div className="docs-terminal-snippet">
              <span className="docs-terminal-prompt">$</span>utim doctor<br />
              <span className="docs-terminal-comment"># Windows PowerShell UTF-8 encoding fix:</span><br />
              <span className="docs-terminal-prompt">$</span>chcp 65001
            </div>
          </div>

        </div>

      </div>

      {/* Footer Component */}
      <ScrollytellingFooter />
    </div>
  );
}
