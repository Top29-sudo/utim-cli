import React from 'react'
import { Helmet } from 'react-helmet-async'

const styles = {
  page: {
    background: '#0d0f18',
    color: '#e6e8ef',
    fontFamily: "'Inter', -apple-system, sans-serif",
    minHeight: '100vh',
    margin: 0,
  },
  hero: {
    maxWidth: '900px',
    margin: '0 auto',
    padding: '80px 24px 48px',
    textAlign: 'center',
  },
  badge: {
    display: 'inline-block',
    background: 'linear-gradient(135deg, #a78bfa22, #7c3aed22)',
    border: '1px solid #a78bfa55',
    borderRadius: '100px',
    padding: '6px 16px',
    fontSize: '13px',
    color: '#a78bfa',
    marginBottom: '24px',
    letterSpacing: '0.04em',
  },
  h1: {
    fontSize: 'clamp(32px, 5vw, 52px)',
    fontWeight: 800,
    lineHeight: 1.1,
    margin: '0 0 20px',
    background: 'linear-gradient(135deg, #fff 0%, #a8b0c2 100%)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    backgroundClip: 'text',
  },
  lead: {
    fontSize: '18px',
    color: '#a8b0c2',
    lineHeight: 1.7,
    maxWidth: '680px',
    margin: '0 auto 40px',
  },
  ctaRow: {
    display: 'flex',
    gap: '12px',
    justifyContent: 'center',
    flexWrap: 'wrap',
    marginBottom: '64px',
  },
  btnPrimary: {
    background: 'linear-gradient(135deg, #7c8cff, #5b6eff)',
    color: '#fff',
    border: 'none',
    borderRadius: '10px',
    padding: '14px 28px',
    fontSize: '15px',
    fontWeight: 600,
    cursor: 'pointer',
    textDecoration: 'none',
    display: 'inline-block',
  },
  btnSecondary: {
    background: 'transparent',
    color: '#a8b0c2',
    border: '1px solid #2a2f44',
    borderRadius: '10px',
    padding: '14px 28px',
    fontSize: '15px',
    fontWeight: 600,
    cursor: 'pointer',
    textDecoration: 'none',
    display: 'inline-block',
  },
  section: {
    maxWidth: '900px',
    margin: '0 auto',
    padding: '0 24px 64px',
  },
  h2: {
    fontSize: '28px',
    fontWeight: 700,
    marginBottom: '24px',
    color: '#fff',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '15px',
    marginBottom: '48px',
  },
  th: {
    padding: '14px 16px',
    textAlign: 'left',
    borderBottom: '1px solid #1f2438',
    color: '#a78bfa',
    fontWeight: 600,
    fontSize: '13px',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },
  td: {
    padding: '14px 16px',
    borderBottom: '1px solid #1a1e30',
    color: '#c8d0e0',
    verticalAlign: 'top',
  },
  trAlt: { background: '#11141f' },
  win: { color: '#4ade80', fontWeight: 600 },
  lose: { color: '#f87171' },
  neutral: { color: '#a8b0c2' },
  verdict: {
    background: 'linear-gradient(135deg, #141826, #1a1630)',
    border: '1px solid #a78bfa44',
    borderRadius: '16px',
    padding: '32px',
    marginBottom: '48px',
  },
  verdictTitle: { fontSize: '20px', fontWeight: 700, color: '#a78bfa', marginBottom: '12px' },
  verdictText: { color: '#c8d0e0', lineHeight: 1.7, fontSize: '16px', margin: 0 },
  faqItem: {
    borderBottom: '1px solid #1a1e30',
    padding: '20px 0',
  },
  faqQ: { fontSize: '16px', fontWeight: 600, color: '#fff', marginBottom: '8px' },
  faqA: { fontSize: '15px', color: '#a8b0c2', lineHeight: 1.7, margin: 0 },
  footer: {
    maxWidth: '900px',
    margin: '0 auto',
    padding: '32px 24px',
    borderTop: '1px solid #1a1e30',
    textAlign: 'center',
    color: '#5a6070',
    fontSize: '14px',
  },
}

const features = [
  { feature: 'Free plan available', utim: '✅ Yes – full agent', ag: '❌ Paid subscription' },
  { feature: 'Runs in any terminal', utim: '✅ npm / pip install', ag: '✅ Yes' },
  { feature: 'Model Context Protocol (MCP)', utim: '✅ Native full support', ag: '⚠️ Via IDE only' },
  { feature: 'Executable miniagents', utim: '✅ Script-based, publishable', ag: '❌ Not available' },
  { feature: 'Creators Marketplace', utim: '✅ Buy, sell & earn 80%', ag: '❌ No marketplace' },
  { feature: 'Vector memory RAG', utim: '✅ ChromaDB built-in', ag: '❌ No persistent memory' },
  { feature: 'Dynamic context compression', utim: '✅ Auto-scales to model', ag: '⚠️ Manual' },
  { feature: 'Dry-run sandboxing', utim: '✅ Safe preview before exec', ag: '❌ No sandbox' },
  { feature: '/undo & /rewind commands', utim: '✅ Full rollback support', ag: '❌ No rollback' },
  { feature: 'Workspace skills system', utim: '✅ Per-project AI rules', ag: '⚠️ Limited rules' },
  { feature: 'Works on Android Termux', utim: '✅ Confirmed support', ag: '❌ Not supported' },
  { feature: 'Multi-model support', utim: '✅ Any API-compatible LLM', ag: '⚠️ Google models focus' },
  { feature: 'Revenue share for creators', utim: '✅ 80% to publisher', ag: '❌ No creator program' },
  { feature: 'Open source components', utim: '✅ Partially open', ag: '❌ Closed source' },
  { feature: 'Pricing', utim: '✅ Free + from $7/mo', ag: '❌ Higher paid tiers only' },
]

const faqs = [
  {
    q: 'Is UTIM AI a good Antigravity alternative?',
    a: 'Yes. UTIM AI offers everything Antigravity does for terminal coding, plus features Antigravity lacks: a completely free plan, a Creators Marketplace where you can monetize your own tools, executable miniagents, vector memory RAG with ChromaDB, /undo and /rewind rollback commands, and dry-run sandboxing. For developers who want more than just an IDE plugin, UTIM is the superior choice.',
  },
  {
    q: 'How is UTIM AI different from Antigravity?',
    a: 'Antigravity is primarily an IDE-integrated AI assistant. UTIM AI is a fully autonomous terminal agent — it runs independently of any IDE, supports any OS including Android Termux, connects to any LLM via API, and includes an open Creators Marketplace where developers can publish, buy, and sell custom tools and miniagents.',
  },
  {
    q: 'Is UTIM AI free unlike Antigravity?',
    a: 'UTIM AI has a full-featured free plan that gives developers access to the complete CLI agent with no credit card required. Antigravity currently requires a paid plan for full access. UTIM\'s free tier makes it accessible to students, indie developers, and open-source contributors without any cost barrier.',
  },
  {
    q: 'Can I switch from Antigravity to UTIM AI easily?',
    a: 'Yes. Install UTIM with `npm install -g @emend-ai/utim` and run `utim` in your terminal. The agent uses the same core workflow — file editing, code generation, shell execution — so the transition is immediate. You\'ll also gain access to features Antigravity doesn\'t offer.',
  },
  {
    q: 'Does UTIM AI work without an IDE like Antigravity requires?',
    a: 'UTIM AI is 100% terminal-native. It requires no IDE, no browser extension, and no GUI. It installs via npm or pip and runs in any terminal on Windows, macOS, Linux, or Android Termux. This makes it more portable and flexible than IDE-bound alternatives like Antigravity.',
  },
]

export default function VsAntigravity() {
  return (
    <div style={styles.page}>
      <Helmet>
        <title>UTIM AI vs Antigravity – Best Antigravity Alternative CLI Agent 2026</title>
        <meta name="description" content="UTIM AI vs Antigravity: feature comparison for terminal developers. UTIM offers a free plan, Creators Marketplace, miniagents, vector memory, and MCP. The best Antigravity alternative." />
        <link rel="canonical" href="https://utim.dev/vs-antigravity" />
        <script type="application/ld+json">{JSON.stringify({
          '@context': 'https://schema.org',
          '@type': 'Article',
          headline: 'UTIM AI vs Antigravity – Best CLI Coding Agent Alternative in 2026',
          description: 'Detailed feature-by-feature comparison of UTIM AI and Antigravity for terminal-first developers.',
          author: { '@type': 'Organization', name: 'Emend AI', url: 'https://utim.dev' },
          publisher: { '@type': 'Organization', name: 'Emend AI', logo: { '@type': 'ImageObject', url: 'https://utim.dev/icon.png' } },
          datePublished: '2026-08-05',
          dateModified: '2026-08-05',
          mainEntityOfPage: { '@type': 'WebPage', '@id': 'https://utim.dev/vs-antigravity' },
        })}</script>
        <script type="application/ld+json">{JSON.stringify({
          '@context': 'https://schema.org',
          '@type': 'FAQPage',
          mainEntity: faqs.map(f => ({
            '@type': 'Question',
            name: f.q,
            acceptedAnswer: { '@type': 'Answer', text: f.a },
          })),
        })}</script>
      </Helmet>

      {/* Hero */}
      <div style={styles.hero}>
        <div style={styles.badge}>UTIM AI vs Antigravity · 2026</div>
        <h1 style={styles.h1}>UTIM AI vs Antigravity:<br />The Best Alternative for Terminal Developers</h1>
        <p style={styles.lead}>
          Antigravity is a capable AI assistant. But UTIM AI is built differently —
          100% terminal-native, free to start, with a Creators Marketplace, miniagents,
          vector memory, and no IDE required. Here's why thousands of developers are switching.
        </p>
        <div style={styles.ctaRow}>
          <a href="/" style={styles.btnPrimary}>Try UTIM AI Free →</a>
          <a href="/features" style={styles.btnSecondary}>See All Features</a>
        </div>
      </div>

      {/* Comparison Table */}
      <div style={styles.section}>
        <h2 style={styles.h2}>Feature-by-Feature Comparison</h2>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Feature</th>
              <th style={styles.th}>UTIM AI</th>
              <th style={styles.th}>Antigravity</th>
            </tr>
          </thead>
          <tbody>
            {features.map((row, i) => (
              <tr key={i} style={i % 2 === 1 ? styles.trAlt : {}}>
                <td style={{ ...styles.td, color: '#e6e8ef', fontWeight: 500 }}>{row.feature}</td>
                <td style={styles.td}><span style={styles.win}>{row.utim}</span></td>
                <td style={styles.td}><span style={row.ag.startsWith('❌') ? styles.lose : styles.neutral}>{row.ag}</span></td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Verdict */}
        <div style={styles.verdict}>
          <div style={styles.verdictTitle}>🏆 Verdict: UTIM AI is the better Antigravity alternative</div>
          <p style={styles.verdictText}>
            Antigravity focuses on IDE-integrated AI assistance. UTIM AI goes further —
            it's fully autonomous, runs in any terminal without an IDE, has a free plan,
            and includes an open Creators Marketplace where developers can publish and monetize
            their own tools and miniagents. For developers who want maximum control, flexibility,
            and zero vendor lock-in,{' '}
            <strong style={{ color: '#e6e8ef' }}>UTIM AI is the best Antigravity alternative available in 2026.</strong>
          </p>
        </div>

        {/* FAQ */}
        <h2 style={styles.h2}>Frequently Asked Questions</h2>
        {faqs.map((faq, i) => (
          <div key={i} style={styles.faqItem}>
            <div style={styles.faqQ}>{faq.q}</div>
            <p style={styles.faqA}>{faq.a}</p>
          </div>
        ))}
      </div>

      <div style={styles.footer}>
        <p>© 2026 Emend AI · <a href="/" style={{ color: '#a78bfa', textDecoration: 'none' }}>utim.dev</a> · <a href="/pricing" style={{ color: '#a78bfa', textDecoration: 'none' }}>Pricing</a> · <a href="/vs-claude-code" style={{ color: '#a78bfa', textDecoration: 'none' }}>vs Claude Code</a></p>
      </div>
    </div>
  )
}
