import React from 'react';
import ScrollytellingHeaderNav from '../../components/ScrollytellingHeaderNav';
import ScrollytellingFooter from '../../components/ScrollytellingFooter';
import SEOHead from '../../components/SEOHead';
import { Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import '../../components/ScrollytellingMain.css';

const features = [
  { feature: 'Free plan available', utim: '✅ Yes – full agent', ag: '✅ Yes – free tier available' },
  { feature: 'Runs in any terminal', utim: '✅ npm / pip install', ag: '✅ Antigravity CLI' },
  { feature: 'Model Context Protocol (MCP)', utim: '✅ Native full support', ag: '✅ Native support' },
  { feature: 'Executable miniagents / subagents', utim: '✅ Script-based miniagents', ag: '✅ Custom & asynchronous subagents' },
  { feature: 'Creators Ecosystem Marketplace', utim: '✅ Buy, sell & earn 95%', ag: '⚠️ Plugins / MCP ecosystem, no equivalent paid creator marketplace verified' },
  { feature: 'Vector experience memory RAG', utim: '✅ ChromaDB persistent semantic memory', ag: '⚠️ No equivalent persistent vector-experience RAG publicly verified' },
  { feature: 'Dynamic context compression', utim: '✅ Auto-scales to selected model', ag: '✅ Automatic context compaction' },
  { feature: 'No-write dry-run mode', utim: '✅ Safe preview before applying changes', ag: '⚠️ Secure sandbox available, but not the same as dry-run preview' },
  { feature: '/undo & /rewind rollback', utim: '✅ Full agent rollback', ag: '⚠️ Version / recovery workflows available, but no equivalent UTIM-style rollback verified' },
  { feature: 'Workspace skills system', utim: '✅ Per-project Skills & AI rules', ag: '✅ Workspace and global Skills' },
  { feature: 'Android Termux support', utim: '✅ Confirmed support', ag: '⚠️ No official Termux support documented' },
  { feature: 'Multi-provider model support', utim: '✅ OpenAI, Claude, Gemini, Ollama & others', ag: '⚠️ Curated models from multiple families' },
  { feature: 'Open model/provider flexibility', utim: '✅ User can choose across supported providers', ag: '⚠️ Limited to models exposed through Antigravity' },
  { feature: 'Marketplace monetization for creators', utim: '✅ Creators can earn 80% from sales', ag: '❌ No equivalent public creator revenue-sharing system verified' },
];

const faqs = [
  {
    q: 'Is UTIM AI a good Antigravity alternative?',
    a: 'Yes. UTIM AI offers everything Antigravity does for terminal coding, plus features Antigravity lacks: a completely free plan, a Creators Marketplace to monetize tools, executable miniagents, vector memory RAG with ChromaDB, and dry-run sandboxing.',
  },
  {
    q: 'How is UTIM AI different from Antigravity?',
    a: 'Antigravity is primarily an IDE assistant. UTIM AI is 100% terminal-native — running independently of any IDE on Windows, macOS, Linux, or Android Termux.',
  },
];

export default function VsAntigravity() {
  return (
    <div className="st-page-root">
      <SEOHead
        title="UTIM AI vs Antigravity — Antigravity Alternative CLI Agent 2026"
        description="UTIM AI vs Antigravity: feature comparison for terminal developers. UTIM offers a free plan, Creators Marketplace, miniagents, vector memory, and MCP. An Antigravity alternative."
        canonical="https://utim.dev/vs-antigravity"
      />
      <ScrollytellingHeaderNav />

      <div style={{ padding: '60px 24px 30px 24px', textAlign: 'center' }}>
        <div className="st-container">
          <h1 className="st-section-title" style={{ fontSize: 'clamp(2.4rem, 4.5vw, 3.6rem)' }}>
            UTIM AI vs Antigravity
          </h1>
          <p className="st-section-subtitle" style={{ maxWidth: 740, margin: '0 auto 24px auto' }}>
            Terminal-first AI coding agent with Creators Marketplace, persistent ChromaDB vector memory RAG, and zero IDE lock-in.
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
                  <th style={{ textAlign: 'center' }}>Antigravity</th>
                </tr>
              </thead>
              <tbody>
                {features.map((row, idx) => (
                  <tr key={idx}>
                    <td className="st-row-feature">{row.feature}</td>
                    <td className="st-row-utim" style={{ textAlign: 'center', color: 'var(--accent-green) !important' }}>{row.utim}</td>
                    <td style={{ textAlign: 'center', color: row.ag.startsWith('❌') ? '#ef4444' : 'var(--text-secondary)' }}>{row.ag}</td>
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
                  <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-muted)' }}>Antigravity</span>
                  <span style={{ fontSize: 12.5, fontWeight: 700, color: row.ag.startsWith('❌') ? '#ef4444' : 'var(--text-secondary)' }}>{row.ag}</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="st-doc-card" style={{ background: 'var(--bg-cream-card)', border: '2px solid var(--accent-black)', marginBottom: 40 }}>
          <h2 className="st-doc-card-title">🏆 Verdict: Why Developers Choose UTIM AI</h2>
          <p style={{ fontSize: '1rem', color: 'var(--text-body)', lineHeight: 1.7 }}>
            UTIM AI is purpose-built for CLI workflows without requiring an IDE window open. It supports native subagents, full file safety rollback, and an open marketplace where developers keep 95% revenue.
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
