import React from 'react';
import { Check, X, ShieldCheck, Zap, Coins, GitBranch, Database, Award, Box, Eye } from 'lucide-react';

export default function ComparisonMatrixSection() {
  const bigFour = [
    {
      title: '95% Creator Marketplace',
      desc: 'Build & sell custom miniagents, tools, and Skills while retaining 95% direct revenue share.',
      icon: Award,
      badge: 'MONETIZATION'
    },
    {
      title: 'Quota Sharing & Redeem Codes',
      desc: 'Transfer quota instantly to team members (`/share`) and redeem non-expiring promo/credit codes.',
      icon: Coins,
      badge: 'CREDIT ECONOMICS'
    },
    {
      title: 'Cross-provider Subagent Routing',
      desc: 'Main agent on Claude/GPT while concurrently offloading subagent tasks to free Gemma/Cohere models.',
      icon: GitBranch,
      badge: 'MULTI-LLM ORCHESTRATION'
    },
    {
      title: 'Persistent Experience & Skill RAG',
      desc: 'ChromaDB vector memory indexing project architectural conventions, past debugging fixes, and Skills.',
      icon: Database,
      badge: 'VECTOR MEMORY RAG'
    }
  ];

  const comparisonData = [
    {
      feature: '95% Creator Revenue Marketplace',
      utim: '✅ Creators sell tools & keep 95%',
      cursor: '❌ Equivalent not verified',
      claudeCode: '❌ Equivalent not verified',
      antigravity: '❌ Equivalent not verified',
      aider: '❌ No marketplace',
    },
    {
      feature: 'User-to-user Quota Sharing',
      utim: '✅ /share quota transfer',
      cursor: '❌ Not available on any competitor',
      claudeCode: '❌ Not available on any competitor',
      antigravity: '❌ Not available on any competitor',
      aider: '❌ Not available on any competitor',
    },
    {
      feature: '3D Model Generator Tool (blender_agent)',
      utim: '✅ Built-in 3D model generator agent',
      cursor: '❌ Not available on any competitor',
      claudeCode: '❌ Not available on any competitor',
      antigravity: '❌ Not available on any competitor',
      aider: '❌ Not available on any competitor',
    },
    {
      feature: 'Synthetic Vision for Non-Vision Models',
      utim: '✅ Converts images for text-only LLMs',
      cursor: '❌ Text models cannot see images',
      claudeCode: '❌ Text models cannot see images',
      antigravity: '❌ Text models cannot see images',
      aider: '❌ Text models cannot see images',
    },
    {
      feature: 'Non-expiring Quota Redeem Codes',
      utim: '✅ Gift & promo code engine',
      cursor: '❌ Not available',
      claudeCode: '❌ Not available',
      antigravity: '❌ Not available',
      aider: '❌ Not available',
    },
    {
      feature: 'ChromaDB Experience Memory RAG',
      utim: '✅ ChromaDB cross-session RAG',
      cursor: '⚠️ Different memory/indexing',
      claudeCode: '⚠️ Different memory',
      antigravity: '⚠️ Different system',
      aider: '❌ No persistent RAG',
    },
    {
      feature: 'Semantic Skill RAG',
      utim: '✅ Vector search over Skills',
      cursor: '⚠️ Skills without vector architecture',
      claudeCode: '⚠️ Skills without vector architecture',
      antigravity: '⚠️ Skills without vector architecture',
      aider: '❌ No Skills RAG',
    },
    {
      feature: 'Universal BYOK + UTIM quota bypass',
      utim: '✅ BYOK bypasses quota engine',
      cursor: '⚠️ Partial BYOK',
      claudeCode: '⚠️ Account key restricted',
      antigravity: '⚠️ Account key restricted',
      aider: '⚠️ Broad BYOK without UTIM quota engine',
    },
    {
      feature: 'Independent Main/Subagent provider routing',
      utim: '✅ Main on Claude, Subagent on Gemma',
      cursor: '⚠️ Single active provider',
      claudeCode: '⚠️ Anthropic models only',
      antigravity: '⚠️ Curated models',
      aider: '❌ No subagents system',
    },
    {
      feature: 'Workspace + complete AI-state /share',
      utim: '✅ /share complete state & sessions',
      cursor: '⚠️ Cloud sharing',
      claudeCode: '⚠️ Session workflows',
      antigravity: '⚠️ Session workflows',
      aider: '❌ No session share',
    },
    {
      feature: 'Live tokens + time + credits + cache economics',
      utim: '✅ Full telemetry & cost breakdown',
      cursor: '⚠️ Partial telemetry',
      claudeCode: '⚠️ Partial telemetry',
      antigravity: '⚠️ Partial telemetry',
      aider: '⚠️ Partial telemetry',
    },
    {
      feature: 'Android Termux support',
      utim: '✅ Official native Termux',
      cursor: '⚠️ No official Termux support',
      claudeCode: '⚠️ No official Termux support',
      antigravity: '⚠️ No official Termux support',
      aider: '⚠️ No official Termux support',
    },
  ];

  const getStatusStyle = (val) => {
    if (val.startsWith('✅')) return { color: '#059669', fontWeight: 700 };
    if (val.startsWith('⚠️')) return { color: '#d97706', fontWeight: 600 };
    return { color: '#ef4444', fontWeight: 500 };
  };

  return (
    <section className="st-comparison-section" id="comparison">
      <div className="st-container">
        <div className="st-section-header">
          <h2 className="st-section-title">
            How UTIM Compares to Competitors
          </h2>
          <p className="st-section-subtitle">
            See why developers choose UTIM's open terminal ecosystem over proprietary lock-in.
          </p>
        </div>

        {/* The Big Four Pillar Cards */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: 16,
          marginBottom: 36
        }}>
          {bigFour.map((item, idx) => {
            const Icon = item.icon;
            return (
              <div key={idx} style={{
                background: '#FFFFFF',
                border: '2px solid var(--accent-black)',
                borderRadius: 14,
                padding: '20px 18px',
                boxShadow: 'var(--shadow-sm)',
                display: 'flex',
                flexDirection: 'column',
                justify: 'space-between'
              }}>
                <div>
                  <div style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    fontSize: 10.5,
                    fontWeight: 800,
                    letterSpacing: '0.06em',
                    color: 'var(--accent-brand)',
                    background: 'var(--bg-cream-alt)',
                    padding: '3px 8px',
                    borderRadius: 6,
                    marginBottom: 12
                  }}>
                    <Icon size={12} /> {item.badge}
                  </div>
                  <h3 style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: 6 }}>
                    {item.title}
                  </h3>
                  <p style={{ fontSize: '0.88rem', color: 'var(--text-body)', lineHeight: 1.5 }}>
                    {item.desc}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Desktop Table View (screens >= 768px) */}
        <div className="st-comparison-card st-desktop-comparison-view">
          <div className="st-table-wrapper">
            <table className="st-comparison-table">
              <thead>
                <tr>
                  <th style={{ width: '32%' }}>UTIM Capability</th>
                  <th className="st-col-utim" style={{ textAlign: 'center', width: '22%' }}>UTIM AI</th>
                  <th style={{ textAlign: 'center', width: '11.5%' }}>Cursor</th>
                  <th style={{ textAlign: 'center', width: '11.5%' }}>Claude Code</th>
                  <th style={{ textAlign: 'center', width: '11.5%' }}>Antigravity</th>
                  <th style={{ textAlign: 'center', width: '11.5%' }}>Aider</th>
                </tr>
              </thead>
              <tbody>
                {comparisonData.map((row, idx) => (
                  <tr key={idx}>
                    <td className="st-row-feature" style={{ fontWeight: 700 }}>{row.feature}</td>
                    <td className="st-row-utim" style={{ textAlign: 'center', fontSize: '0.86rem', ...getStatusStyle(row.utim) }}>
                      {row.utim}
                    </td>
                    <td style={{ textAlign: 'center', fontSize: '0.84rem', ...getStatusStyle(row.cursor) }}>
                      {row.cursor}
                    </td>
                    <td style={{ textAlign: 'center', fontSize: '0.84rem', ...getStatusStyle(row.claudeCode) }}>
                      {row.claudeCode}
                    </td>
                    <td style={{ textAlign: 'center', fontSize: '0.84rem', ...getStatusStyle(row.antigravity) }}>
                      {row.antigravity}
                    </td>
                    <td style={{ textAlign: 'center', fontSize: '0.84rem', ...getStatusStyle(row.aider) }}>
                      {row.aider}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Mobile Clean Card View (screens < 768px) */}
        <div className="st-mobile-comparison-view">
          {comparisonData.map((row, idx) => (
            <div key={idx} className="st-mobile-comp-card">
              <div className="st-mobile-comp-header">
                <ShieldCheck size={18} color="var(--accent-brand)" style={{ flexShrink: 0, marginTop: 2 }} />
                <h3 className="st-mobile-comp-title">{row.feature}</h3>
              </div>

              <div className="st-mobile-comp-body">
                <div className="st-mobile-comp-utim-row" style={{ padding: '10px 12px' }}>
                  <span className="st-mobile-comp-label">UTIM AI</span>
                  <span style={{ fontSize: 13, ...getStatusStyle(row.utim) }}>
                    {row.utim}
                  </span>
                </div>

                <div className="st-mobile-comp-others-grid" style={{ gap: 6, marginTop: 8 }}>
                  <div className="st-mobile-comp-other-item">
                    <span className="st-other-name">Cursor:</span>
                    <span style={{ fontSize: 12, ...getStatusStyle(row.cursor) }}>{row.cursor}</span>
                  </div>
                  <div className="st-mobile-comp-other-item">
                    <span className="st-other-name">Claude Code:</span>
                    <span style={{ fontSize: 12, ...getStatusStyle(row.claudeCode) }}>{row.claudeCode}</span>
                  </div>
                  <div className="st-mobile-comp-other-item">
                    <span className="st-other-name">Antigravity:</span>
                    <span style={{ fontSize: 12, ...getStatusStyle(row.antigravity) }}>{row.antigravity}</span>
                  </div>
                  <div className="st-mobile-comp-other-item">
                    <span className="st-other-name">Aider:</span>
                    <span style={{ fontSize: 12, ...getStatusStyle(row.aider) }}>{row.aider}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
