import { Helmet } from 'react-helmet-async'

const BASE_URL = 'https://utim.dev'
const DEFAULT_IMAGE = `${BASE_URL}/1.png`

const SEO_MAP = {
  '/': {
    title: 'UTIM AI – Best CLI AI Coding Agent | Claude Code & Antigravity Alternative',
    description:
      'UTIM AI is the fastest-growing CLI coding agent for developers. Better than Claude Code and Antigravity – free plan, MCP support, miniagents, Creators Marketplace. Install in 30 seconds.',
    keywords:
      'best cli ai agent, claude code alternative, antigravity alternative, better cli agent than claude, ai terminal coding assistant, autonomous cli agent, utim ai, terminal ai coding, mcp server cli, cli coding agent free',
  },
  '/features': {
    title: 'UTIM AI Features – MCP, Miniagents, Memory RAG | Better Than Claude Code CLI',
    description:
      'UTIM AI features: autonomous think-act-observe loop, Model Context Protocol (MCP), vector memory RAG, dynamic context compression, Creators Marketplace, dry-run sandbox, and executable miniagents.',
    keywords:
      'cli ai agent features, mcp cli agent, miniagents terminal, cli memory rag, autonomous coding agent features, claude code alternative features',
  },
  '/pricing': {
    title: 'UTIM AI Pricing – Free CLI Agent Plan | No Credit Card Required',
    description:
      'UTIM AI pricing: Free plan for developers with full CLI agent access. Pro plans with unlimited cloud miniagents, priority MCP, and Creators Marketplace revenue share. No credit card for free tier.',
    keywords:
      'utim ai pricing, cli ai agent free plan, free coding agent, claude code pricing comparison, antigravity pricing alternative, best free cli agent',
  },
  '/docs': {
    title: 'UTIM AI Docs – CLI Agent Documentation & Setup Guide',
    description:
      'Full documentation for UTIM AI CLI: installation, configuration, MCP servers, miniagents, workspace skills, memory RAG, and the Creators Marketplace API.',
    keywords:
      'utim ai docs, cli agent documentation, how to install utim, mcp cli setup, utim miniagents guide',
  },
  '/about': {
    title: 'About UTIM AI – The Team Behind the Best CLI Coding Agent',
    description:
      'Learn about Emend AI and the team building UTIM AI – the autonomous CLI coding agent designed for developers who live in the terminal.',
    keywords: 'utim ai team, emend ai, about utim, cli coding agent company',
  },
  '/marketplace': {
    title: 'UTIM Creators Marketplace – Buy & Sell CLI Tools, Miniagents & Skills',
    description:
      'The UTIM Creators Marketplace: discover, install, and monetize custom CLI tools, workspace skills, and executable miniagents. First 100 creators pay zero platform fees.',
    keywords:
      'sell cli tools, sell miniagent, monetize ai agent, cli tools marketplace, publish ai tool, buy cli skills',
  },
  '/changelog': {
    title: 'UTIM AI Changelog – Latest Updates & Releases',
    description:
      'Follow UTIM AI version updates, new features, bug fixes, and improvements to the CLI coding agent.',
    keywords: 'utim changelog, utim ai updates, cli agent releases',
  },
  '/vs-claude-code': {
    title: 'UTIM AI vs Claude Code – Best CLI Coding Agent Comparison 2026',
    description:
      'UTIM AI vs Claude Code: detailed feature-by-feature comparison. See why developers switch to UTIM for terminal coding – free plan, MCP, miniagents, marketplace, and more.',
    keywords:
      'utim vs claude code, claude code alternative, better than claude code, claude code cli comparison, best cli coding agent 2026',
    schema: {
      '@type': 'Article',
      headline: 'UTIM AI vs Claude Code – Which CLI Coding Agent Is Better?',
      description:
        'An in-depth comparison of UTIM AI and Claude Code for terminal-first developers.',
      author: { '@type': 'Organization', name: 'Emend AI' },
      datePublished: '2026-08-05',
    },
  },
  '/vs-antigravity': {
    title: 'UTIM AI vs Antigravity – CLI Agent Comparison | Best Alternative 2026',
    description:
      'UTIM AI vs Antigravity CLI: compare features, pricing, MCP support, and marketplace. Find out why UTIM is the top Antigravity alternative for developers in 2026.',
    keywords:
      'utim vs antigravity, antigravity alternative, better than antigravity, antigravity cli comparison, best antigravity alternative 2026',
    schema: {
      '@type': 'Article',
      headline: 'UTIM AI vs Antigravity – Which CLI Coding Agent Wins in 2026?',
      description:
        'A detailed comparison of UTIM AI and Antigravity CLI for developers.',
      author: { '@type': 'Organization', name: 'Emend AI' },
      datePublished: '2026-08-05',
    },
  },
  '/referral': {
    title: 'UTIM AI Referral Program – Earn Free Pro Credits',
    description:
      'Refer developers to UTIM AI and earn free Pro credits. Share your referral link and get rewarded when your friends upgrade.',
    keywords: 'utim referral, cli agent referral program, earn utim credits',
  },
  '/support': {
    title: 'UTIM AI Support – Help Center & Contact',
    description:
      'Get help with UTIM AI CLI: installation issues, billing, MCP configuration, and more. Contact our support team or browse the help center.',
    keywords: 'utim support, cli agent help, utim ai contact',
  },
}

export default function SEOHead({ path }) {
  const seo = SEO_MAP[path] || SEO_MAP['/']
  const canonical = `${BASE_URL}${path === '/' ? '' : path}`
  const ogImage = seo.image || DEFAULT_IMAGE

  return (
    <Helmet>
      <title>{seo.title}</title>
      <meta name="title" content={seo.title} />
      <meta name="description" content={seo.description} />
      {seo.keywords && <meta name="keywords" content={seo.keywords} />}
      <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1" />
      <link rel="canonical" href={canonical} />

      {/* OpenGraph */}
      <meta property="og:type" content="website" />
      <meta property="og:url" content={canonical} />
      <meta property="og:site_name" content="UTIM AI" />
      <meta property="og:title" content={seo.title} />
      <meta property="og:description" content={seo.description} />
      <meta property="og:image" content={ogImage} />
      <meta property="og:image:width" content="1200" />
      <meta property="og:image:height" content="630" />
      <meta property="og:locale" content="en_US" />

      {/* Twitter */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:url" content={canonical} />
      <meta name="twitter:site" content="@utim_ai" />
      <meta name="twitter:title" content={seo.title} />
      <meta name="twitter:description" content={seo.description} />
      <meta name="twitter:image" content={ogImage} />

      {/* Per-page JSON-LD if defined */}
      {seo.schema && (
        <script type="application/ld+json">
          {JSON.stringify({
            '@context': 'https://schema.org',
            ...seo.schema,
            url: canonical,
          })}
        </script>
      )}
    </Helmet>
  )
}
