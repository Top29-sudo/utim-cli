import React from 'react';
import ScrollytellingHeaderNav from '../../components/ScrollytellingHeaderNav';
import ScrollytellingFooter from '../../components/ScrollytellingFooter';
import SEOHead from '../../components/SEOHead';
import { Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import '../../components/ScrollytellingMain.css';

const features = [
  { feature: 'Free plan', utim: '✅ Available', cursor: '✅ Hobby — limited Agent usage' },
  { feature: 'Terminal-first agent', utim: '✅ Native CLI', cursor: '✅ Cursor CLI' },
  { feature: 'npm / pip distribution', utim: '✅ npm / pip*', cursor: '❌ Separate Cursor installer' },
  { feature: 'MCP', utim: '✅ Supported', cursor: '✅ Supported' },
  { feature: 'Specialized subagents', utim: '✅ Miniagents', cursor: '✅ Subagents' },
  { feature: 'Creator monetization marketplace', utim: '✅ Creators can sell & earn 80%*', cursor: '⚠️ Plugin Marketplace; different monetization model' },
  { feature: 'Persistent experience-memory RAG', utim: '✅ ChromaDB cross-session memory*', cursor: '⚠️ Semantic codebase indexing; not equivalent' },
  { feature: 'Agent dry-run mode', utim: '✅ Preview without committing*', cursor: '⚠️ Has sandboxing/checkpoints, but different purpose' },
  { feature: 'Rollback', utim: '✅ /undo + /rewind*', cursor: '✅ Local Checkpoints' },
  { feature: 'Android / Termux', utim: '✅ Official support*', cursor: '⚠️ No official Termux support documented' },
];

const faqs = [
  {
    q: 'Can I use UTIM AI without opening Cursor IDE?',
    a: 'Yes! UTIM AI runs directly inside your preferred terminal — Zsh, Bash, PowerShell, Tmux, or Termux — with zero external IDE dependencies.',
  },
  {
    q: 'Does UTIM AI have a free tier like Cursor?',
    a: 'UTIM AI provides a forever-free plan with 1,000 monthly credits and access to free open models, whereas Cursor requires a Pro plan after trial exhaustion.',
  },
];

export default function VsCursor() {
  return (
    <div className="st-page-root">
      <SEOHead
        title="UTIM AI vs Cursor — CLI Agent vs IDE Fork 2026"
        description="UTIM AI vs Cursor CLI comparison. UTIM is 100% terminal-native, works in any shell, and offers a free plan with vector memory."
        canonical="https://utim.dev/vs-cursor"
      />
      <ScrollytellingHeaderNav />

      <div style={{ padding: '60px 24px 30px 24px', textAlign: 'center' }}>
        <div className="st-container">
          <h1 className="st-section-title" style={{ fontSize: 'clamp(2.4rem, 4.5vw, 3.6rem)' }}>
            UTIM AI vs Cursor
          </h1>
          <p className="st-section-subtitle" style={{ maxWidth: 740, margin: '0 auto 24px auto' }}>
            Cursor is an IDE fork. UTIM AI is 100% terminal-native — allowing you to stay in your preferred shell and editor without vendor lock-in.
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
                  <th style={{ textAlign: 'center' }}>Cursor CLI</th>
                </tr>
              </thead>
              <tbody>
                {features.map((row, idx) => (
                  <tr key={idx}>
                    <td className="st-row-feature">{row.feature}</td>
                    <td className="st-row-utim" style={{ textAlign: 'center', color: 'var(--accent-green) !important' }}>{row.utim}</td>
                    <td style={{ textAlign: 'center', color: row.cursor.startsWith('❌') ? '#ef4444' : 'var(--text-secondary)' }}>{row.cursor}</td>
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
                  <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-muted)' }}>Cursor CLI</span>
                  <span style={{ fontSize: 12.5, fontWeight: 700, color: row.cursor.startsWith('❌') ? '#ef4444' : 'var(--text-secondary)' }}>{row.cursor}</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="st-doc-card" style={{ background: 'var(--bg-cream-card)', border: '2px solid var(--accent-black)', marginBottom: 40 }}>
          <h2 className="st-doc-card-title">🏆 Verdict: Why Developers Choose UTIM AI</h2>
          <p style={{ fontSize: '1rem', color: 'var(--text-body)', lineHeight: 1.7 }}>
            UTIM AI eliminates IDE lock-in, runs everywhere from remote servers to Android Termux, and supports native MCP tool plugins out of the box.
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
