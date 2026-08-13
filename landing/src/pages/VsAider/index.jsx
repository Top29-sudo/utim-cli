import React from 'react';
import ScrollytellingHeaderNav from '../../components/ScrollytellingHeaderNav';
import ScrollytellingFooter from '../../components/ScrollytellingFooter';
import SEOHead from '../../components/SEOHead';
import { Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import '../../components/ScrollytellingMain.css';

const features = [
  { feature: 'Free plan available', utim: '✅ Yes – full agent', aider: '⚠️ Aider is free/open-source; model/API access may require BYOK' },
  { feature: 'Runs in any terminal', utim: '✅ npm / pip install', aider: '✅ Yes – terminal-native' },
  { feature: 'Model Context Protocol (MCP)', utim: '✅ Native full support', aider: '❌ No native MCP support' },
  { feature: 'Executable miniagents', utim: '✅ Script-based subagents', aider: '❌ No native subagent/miniagent system' },
  { feature: 'Creators Ecosystem Marketplace', utim: '✅ Buy, sell & earn 95%', aider: '❌ No integrated marketplace' },
  { feature: 'Vector experience memory RAG', utim: '✅ ChromaDB persistent semantic memory', aider: '❌ No persistent vector-memory RAG' },
  { feature: 'Dry-run mode', utim: '✅ Safe preview mode', aider: '✅ --dry-run without modifying files' },
  { feature: '/undo & /rewind rollback', utim: '✅ Full agent rollback', aider: '⚠️ /undo available, Git-based' },
  { feature: 'Android Termux support', utim: '✅ Confirmed support', aider: '⚠️ No official Termux support documented' },
  { feature: 'Multi-model support', utim: '✅ OpenAI, Claude, Gemini, Ollama & others', aider: '✅ Broad cloud + local LLM support' },
];

const faqs = [
  {
    q: 'How does UTIM AI compare to Aider?',
    a: 'While Aider is a solid git-pair-programming CLI, UTIM AI is a full autonomous agent featuring multi-step planning loops, native MCP tools, vector memory RAG, and an integrated subagent marketplace.',
  },
  {
    q: 'Can I use my own API keys (BYOK) with UTIM AI like Aider?',
    a: 'Yes! UTIM AI fully supports Bring-Your-Own-Key (BYOK) for any OpenAI-compatible provider, bypassing quota limits entirely.',
  },
];

export default function VsAider() {
  return (
    <div className="st-page-root">
      <SEOHead
        title="UTIM AI vs Aider — CLI Pair Programming Agent Comparison 2026"
        description="UTIM AI vs Aider CLI comparison. UTIM offers native MCP, ChromaDB memory RAG, miniagents, and a free tier."
        canonical="https://utim.dev/vs-aider"
      />
      <ScrollytellingHeaderNav />

      <div style={{ padding: '60px 24px 30px 24px', textAlign: 'center' }}>
        <div className="st-container">
          <h1 className="st-section-title" style={{ fontSize: 'clamp(2.4rem, 4.5vw, 3.6rem)' }}>
            UTIM AI vs Aider
          </h1>
          <p className="st-section-subtitle" style={{ maxWidth: 740, margin: '0 auto 24px auto' }}>
            Aider is a git-based pairing tool. UTIM AI is a full autonomous agent platform with native MCP tools, ChromaDB memory RAG, and subagents.
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
                  <th style={{ textAlign: 'center' }}>Aider</th>
                </tr>
              </thead>
              <tbody>
                {features.map((row, idx) => (
                  <tr key={idx}>
                    <td className="st-row-feature">{row.feature}</td>
                    <td className="st-row-utim" style={{ textAlign: 'center', color: 'var(--accent-green) !important' }}>{row.utim}</td>
                    <td style={{ textAlign: 'center', color: row.aider.startsWith('❌') ? '#ef4444' : 'var(--text-secondary)' }}>{row.aider}</td>
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
                  <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-muted)' }}>Aider</span>
                  <span style={{ fontSize: 12.5, fontWeight: 700, color: row.aider.startsWith('❌') ? '#ef4444' : 'var(--text-secondary)' }}>{row.aider}</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="st-doc-card" style={{ background: 'var(--bg-cream-card)', border: '2px solid var(--accent-black)', marginBottom: 40 }}>
          <h2 className="st-doc-card-title">🏆 Verdict: Why Developers Choose UTIM AI</h2>
          <p style={{ fontSize: '1rem', color: 'var(--text-body)', lineHeight: 1.7 }}>
            UTIM AI offers complete multi-step autonomous planning, self-healing code edits, and Model Context Protocol (MCP) integrations that elevate your terminal beyond simple code diffing.
          </p>
        </div>

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
