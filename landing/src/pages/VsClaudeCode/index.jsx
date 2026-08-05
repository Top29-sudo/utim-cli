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
    background: 'linear-gradient(135deg, #7c8cff22, #5b6eff22)',
    border: '1px solid #7c8cff55',
    borderRadius: '100px',
    padding: '6px 16px',
    fontSize: '13px',
    color: '#7c8cff',
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
    color: '#7c8cff',
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
    background: 'linear-gradient(135deg, #141826, #1a1f3a)',
    border: '1px solid #7c8cff44',
    borderRadius: '16px',
    padding: '32px',
    marginBottom: '48px',
  },
  verdictTitle: { fontSize: '20px', fontWeight: 700, color: '#7c8cff', marginBottom: '12px' },
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
  { feature: 'Free plan available', utim: '✅ Yes – full agent', claude: '❌ Paid only (Pro $20/mo)' },
  { feature: 'Runs in any terminal', utim: '✅ npm / pip install', claude: '✅ Yes' },
  { feature: 'Model Context Protocol (MCP)', utim: '✅ Native full support', claude: '⚠️ Limited / beta' },
  { feature: 'Executable miniagents', utim: '✅ Script-based, publishable', claude: '❌ Not supported' },
  { feature: 'Creators Marketplace', utim: '✅ Buy, sell & monetize tools', claude: '❌ No marketplace' },
  { feature: 'Vector memory RAG', utim: '✅ ChromaDB built-in', claude: '❌ No persistent memory' },
  { feature: 'Dynamic context compression', utim: '✅ Scales to any model', claude: '⚠️ Manual management' },
  { feature: 'Dry-run sandboxing', utim: '✅ /dry-run before exec', claude: '❌ No sandbox mode' },
  { feature: '/undo & /rewind commands', utim: '✅ Full rollback support', claude: '❌ No rollback' },
  { feature: 'Workspace skills system', utim: '✅ Per-project AI rules', claude: '❌ Not available' },
  { feature: 'Works on Android Termux', utim: '✅ Confirmed support', claude: '❌ Not supported' },
  { feature: 'Multi-model support', utim: '✅ Any API-compatible LLM', claude: '⚠️ Anthropic models only' },
  { feature: 'Revenue share for creators', utim: '✅ 80% to publisher', claude: '❌ No creator program' },
  { feature: 'Pricing', utim: '✅ Free + paid plans from $7', claude: '❌ $20/month minimum' },
]

const faqs = [
  {
    q: 'Is UTIM AI really better than Claude Code for terminal developers?',
    a: 'For terminal-first developers, UTIM AI offers a significantly broader feature set: a free plan, native MCP support, executable miniagents, a Creators Marketplace, vector memory RAG, and dry-run sandboxing — none of which Claude Code currently supports. Claude Code is strong for conversational coding, but UTIM is purpose-built for autonomous terminal workflows.',
  },
  {
    q: 'Can I use UTIM AI for free instead of Claude Code?',
    a: 'Yes. UTIM AI offers a completely free plan with the full CLI agent included. Claude Code requires a Claude Pro subscription ($20/month) to use. If budget is a concern, UTIM is the obvious choice.',
  },
  {
    q: 'Does UTIM AI support Model Context Protocol (MCP) like Claude?',
    a: 'UTIM AI has native, full MCP support allowing you to connect any MCP-compatible tool server — databases, browsers, file systems, internal APIs — directly in your terminal. Claude\'s MCP support is currently limited and in beta.',
  },
  {
    q: 'How do I switch from Claude Code to UTIM AI?',
    a: 'Run `npm install -g @emend-ai/utim` or `pip install utim` and type `utim` in your terminal. Your existing workflow transfers immediately — UTIM supports the same file editing, shell execution, and code generation tasks, with additional features like /undo, miniagents, and the Creators Marketplace.',
  },
  {
    q: 'What models does UTIM AI support?',
    a: 'UTIM AI supports any API-compatible LLM — Claude, GPT-4, Gemini, Mistral, and local models via Ollama. Claude Code only works with Anthropic models. This gives UTIM users far more flexibility in cost and capability.',
  },
]

export default function VsClaudeCode() {
  return (
    <div style={styles.page}>
      <Helmet>
        <title>UTIM AI vs Claude Code – Best CLI Coding Agent Comparison 2026</title>
        <meta name="description" content="UTIM AI vs Claude Code: detailed feature comparison. UTIM offers a free plan, native MCP, miniagents, Creators Marketplace, and vector memory — Claude Code does not. Switch today." />
        <link rel="canonical" href="https://utim.dev/vs-claude-code" />
        <script type="application/ld+json">{JSON.stringify({
          '@context': 'https://schema.org',
          '@type': 'Article',
          headline: 'UTIM AI vs Claude Code – Which CLI Coding Agent Is Better in 2026?',
          description: 'Detailed feature-by-feature comparison of UTIM AI and Claude Code for terminal developers.',
          author: { '@type': 'Organization', name: 'Emend AI', url: 'https://utim.dev' },
          publisher: { '@type': 'Organization', name: 'Emend AI', logo: { '@type': 'ImageObject', url: 'https://utim.dev/icon.png' } },
          datePublished: '2026-08-05',
          dateModified: '2026-08-05',
          mainEntityOfPage: { '@type': 'WebPage', '@id': 'https://utim.dev/vs-claude-code' },
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
        <div style={styles.badge}>UTIM AI vs Claude Code · 2026</div>
        <h1 style={styles.h1}>UTIM AI vs Claude Code:<br />Which CLI Coding Agent Wins?</h1>
        <p style={styles.lead}>
          Claude Code is great for conversational AI. But for developers who live in the terminal,
          UTIM AI offers a free plan, native MCP support, miniagents, a Creators Marketplace,
          vector memory, and dry-run sandboxing — features Claude Code simply doesn't have.
        </p>
        <div style={styles.ctaRow}>
          <a href="/" style={styles.btnPrimary}>Try UTIM AI Free →</a>
          <a href="/pricing" style={styles.btnSecondary}>See Pricing</a>
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
              <th style={styles.th}>Claude Code</th>
            </tr>
          </thead>
          <tbody>
            {features.map((row, i) => (
              <tr key={i} style={i % 2 === 1 ? styles.trAlt : {}}>
                <td style={{ ...styles.td, color: '#e6e8ef', fontWeight: 500 }}>{row.feature}</td>
                <td style={styles.td}><span style={styles.win}>{row.utim}</span></td>
                <td style={styles.td}><span style={row.claude.startsWith('❌') ? styles.lose : styles.neutral}>{row.claude}</span></td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Verdict */}
        <div style={styles.verdict}>
          <div style={styles.verdictTitle}>🏆 Verdict: UTIM AI wins for terminal developers</div>
          <p style={styles.verdictText}>
            Claude Code is a polished conversational assistant backed by Anthropic. But it costs $20/month minimum,
            lacks a Creators Marketplace, has no miniagent system, no dry-run sandbox, and no vector memory RAG.
            UTIM AI is purpose-built for autonomous terminal workflows — with a generous free plan, full MCP support,
            and an open ecosystem where developers can publish and monetize their own tools.
            <strong style={{ color: '#e6e8ef' }}> If you want the best CLI coding agent that doesn't lock you into one model or one company, UTIM AI is the clear choice.</strong>
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
        <p>© 2026 Emend AI · <a href="/" style={{ color: '#7c8cff', textDecoration: 'none' }}>utim.dev</a> · <a href="/pricing" style={{ color: '#7c8cff', textDecoration: 'none' }}>Pricing</a> · <a href="/features" style={{ color: '#7c8cff', textDecoration: 'none' }}>Features</a></p>
      </div>
    </div>
  )
}
