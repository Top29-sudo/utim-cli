import React from 'react';
import ScrollytellingHeaderNav from '../../components/ScrollytellingHeaderNav';
import ScrollytellingFooter from '../../components/ScrollytellingFooter';
import SEOHead from '../../components/SEOHead';
import { Sparkles, Check, X, Terminal, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import '../../components/ScrollytellingMain.css';

const features = [
  { feature: 'Free agent tier', utim: '✅ Available*', claude: '⚠️ Claude has Free; Claude Code access/auth varies by plan' },
  { feature: 'Terminal-native', utim: '✅', claude: '✅' },
  { feature: 'MCP support', utim: '✅', claude: '✅' },
  { feature: 'Specialized subagents', utim: '✅ Miniagents*', claude: '✅ Subagents' },
  { feature: 'Paid creator marketplace', utim: '✅ Sell tools/Skills/miniagents + 95% share*', claude: '⚠️ Plugin Marketplace; different creator model' },
  { feature: 'Vector experience-memory RAG', utim: '✅ ChromaDB semantic retrieval*', claude: '⚠️ Auto memory / persistent files, different architecture' },
  { feature: 'Automatic context compression', utim: '✅ Model-aware*', claude: '✅ Auto-compaction' },
  { feature: 'No-write dry-run mode', utim: '✅*', claude: '⚠️ Sandbox/checkpoints instead' },
  { feature: 'Agent rollback / rewind', utim: '✅ /undo + /rewind*', claude: '✅ /rewind + checkpoints' },
  { feature: 'Workspace Skills', utim: '✅', claude: '✅' },
  { feature: 'Android Termux CLI', utim: '✅ Officially supported/tested*', claude: '⚠️ No official Termux support documented' },
  { feature: 'Multi-provider/model routing', utim: '✅ OpenAI, Claude, Gemini, Ollama, etc.*', claude: '⚠️ Claude-family models officially' },
];

const faqs = [
  {
    q: 'Is UTIM AI really better than Claude Code for terminal developers?',
    a: 'For terminal-first developers, UTIM AI offers a broader feature set: a free tier, native MCP support, executable miniagents, a Creators Marketplace, vector memory RAG, and dry-run sandboxing — features Claude Code does not support.',
  },
  {
    q: 'Can I use UTIM AI for free instead of Claude Code?',
    a: 'Yes. UTIM AI offers a completely free plan with the full CLI agent included. Claude Code requires a Claude Pro subscription ($20/month) to use.',
  },
  {
    q: 'Does UTIM AI support Model Context Protocol (MCP)?',
    a: 'UTIM AI has native, full MCP support allowing you to connect any MCP-compatible tool server (databases, browsers, filesystems, APIs) directly in your terminal.',
  },
  {
    q: 'How do I switch from Claude Code to UTIM AI?',
    a: 'Run npm install -g @emend-ai/utim or pip install utim and type utim in your terminal. Your workflow transfers immediately.',
  },
];

export default function VsClaudeCode() {
  return (
    <div className="st-page-root">
      <SEOHead
        title="UTIM AI vs Claude Code — CLI Coding Agent Comparison 2026"
        description="UTIM AI vs Claude Code: detailed feature comparison. UTIM offers a free plan, native MCP, miniagents, Creators Marketplace, and vector memory. Switch today."
        canonical="https://utim.dev/vs-claude-code"
      />
      <ScrollytellingHeaderNav />

      <div style={{ padding: '60px 24px 30px 24px', textAlign: 'center' }}>
        <div className="st-container">
          <h1 className="st-section-title" style={{ fontSize: 'clamp(2.4rem, 4.5vw, 3.6rem)' }}>
            UTIM AI vs Claude Code
          </h1>
          <p className="st-section-subtitle" style={{ maxWidth: 740, margin: '0 auto 24px auto' }}>
            Claude Code is strong for conversational coding. UTIM AI is purpose-built for autonomous terminal workflows — featuring a free tier, native MCP, miniagents, vector memory RAG, and an open Creators Marketplace.
          </p>
        </div>
      </div>

      <div className="st-container" style={{ paddingBottom: 80 }}>
        {/* Desktop Table View (screens >= 768px) */}
        <div className="st-comparison-card st-desktop-comparison-view" style={{ marginBottom: 40 }}>
          <div className="st-table-wrapper">
            <table className="st-comparison-table">
              <thead>
                <tr>
                  <th style={{ width: '40%' }}>Feature Capability</th>
                  <th className="st-col-utim" style={{ textAlign: 'center' }}>UTIM AI</th>
                  <th style={{ textAlign: 'center' }}>Claude Code</th>
                </tr>
              </thead>
              <tbody>
                {features.map((row, idx) => (
                  <tr key={idx}>
                    <td className="st-row-feature">{row.feature}</td>
                    <td className="st-row-utim" style={{ textAlign: 'center', color: 'var(--accent-green) !important' }}>{row.utim}</td>
                    <td style={{ textAlign: 'center', color: row.claude.startsWith('❌') ? '#ef4444' : 'var(--text-secondary)' }}>{row.claude}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Mobile Clean Card Stack (screens < 768px) */}
        <div className="st-mobile-comparison-view" style={{ marginBottom: 40 }}>
          {features.map((row, idx) => (
            <div key={idx} className="st-mobile-comp-card">
              <div className="st-mobile-comp-header">
                <h3 className="st-mobile-comp-title">{row.feature}</h3>
              </div>
              <div className="st-mobile-comp-body" style={{ gap: 8 }}>
                <div className="st-mobile-comp-utim-row" style={{ padding: '8px 12px' }}>
                  <span className="st-mobile-comp-label" style={{ fontSize: 13 }}>UTIM AI</span>
                  <span style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--accent-green)' }}>{row.utim}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', background: 'var(--bg-cream-alt)', borderRadius: 8 }}>
                  <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-muted)' }}>Claude Code</span>
                  <span style={{ fontSize: 12.5, fontWeight: 700, color: row.claude.startsWith('❌') ? '#ef4444' : 'var(--text-secondary)' }}>{row.claude}</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Verdict Box */}
        <div className="st-doc-card" style={{ background: 'var(--bg-cream-card)', border: '2px solid var(--accent-black)', marginBottom: 40 }}>
          <h2 className="st-doc-card-title">🏆 Verdict: Why Developers Choose UTIM AI</h2>
          <p style={{ fontSize: '1rem', color: 'var(--text-body)', lineHeight: 1.7 }}>
            UTIM AI provides full autonomous agent capabilities without forcing a $20/month subscription or single-model vendor lock-in. With native MCP integration, miniagents, and a global Creators Marketplace, UTIM AI is the complete terminal partner.
          </p>
        </div>

        {/* FAQs */}
        <div className="st-doc-card" style={{ marginBottom: 40 }}>
          <h2 className="st-doc-card-title">Frequently Asked Questions</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18, marginTop: 14 }}>
            {faqs.map((faq, idx) => (
              <div key={idx} style={{ borderBottom: '1px solid var(--border-light)', paddingBottom: 14 }}>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: 6 }}>{faq.q}</h3>
                <p style={{ fontSize: '0.94rem', color: 'var(--text-body)', lineHeight: 1.6 }}>{faq.a}</p>
              </div>
            ))}
          </div>
        </div>

        {/* CTA */}
        <div style={{ textAlign: 'center' }}>
          <Link to="/auth" className="st-nav-primary-btn" style={{ padding: '12px 28px', fontSize: 15 }}>
            Get Started with UTIM AI Free →
          </Link>
        </div>
      </div>

      <ScrollytellingFooter />
    </div>
  );
}
