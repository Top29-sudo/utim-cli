import { Helmet } from 'react-helmet-async'

const BASE_URL = 'https://utim.dev'
const DEFAULT_IMAGE = `${BASE_URL}/1.png`

const SEO_MAP = {
  '/': {
    title: 'UTIM AI – Autonomous CLI AI Coding Agent | Claude Code & Antigravity Alternative',
    description:
      'UTIM AI is the fastest-growing CLI coding agent for developers. Better than Claude Code and Antigravity – free plan, MCP support, miniagents, Creators Marketplace. Install in 30 seconds.',
    keywords:
      'autonomous cli ai agent, claude code alternative, antigravity alternative, better cli agent than claude, ai terminal coding assistant, autonomous cli agent, utim ai, terminal ai coding, mcp server cli, cli coding agent free, best free cli tools, open source cli coding agent',
    schema: {
      '@graph': [
        {
          '@type': 'SoftwareApplication',
          'name': 'UTIM AI CLI',
          'description': 'The ultimate local-first autonomous terminal AI coding agent. Integrates native Model Context Protocol (MCP) servers, ChromaDB semantic memory, and multi-model switching.',
          'operatingSystem': 'Windows, macOS, Linux, Android Termux',
          'applicationCategory': 'DeveloperApplication',
          'applicationSubCategory': 'AI Coding Assistant, Terminal Developer Tools',
          'softwareVersion': '2.1.3',
          'downloadUrl': 'https://utim.dev/docs',
          'releaseNotes': 'https://utim.dev/changelog',
          'offers': {
            '@type': 'AggregateOffer',
            'priceCurrency': 'USD',
            'lowPrice': '0',
            'highPrice': '110',
            'offerCount': '5',
            'offers': [
              { '@type': 'Offer', 'name': 'Free Plan', 'price': '0', 'priceCurrency': 'USD' },
              { '@type': 'Offer', 'name': 'Hobby Plan', 'price': '7', 'priceCurrency:': 'USD' },
              { '@type': 'Offer', 'name': 'Pro Plan', 'price': '25', 'priceCurrency': 'USD' },
              { '@type': 'Offer', 'name': 'Max Plan', 'price': '55', 'priceCurrency': 'USD' },
              { '@type': 'Offer', 'name': 'Ultimate Plan', 'price': '110', 'priceCurrency': 'USD' }
            ]
          },
          'featureList': [
            'Autonomous think-act-observe terminal coding loop',
            'Model Context Protocol (MCP) stdio and SSE support',
            'Multi-model provider switching (Claude, GPT, DeepSeek, Ollama)',
            'Local ChromaDB semantic vector RAG memory',
            'Reversible terminal sandbox safety with /undo and /rewind',
            'Creators Marketplace with 95% revenue share'
          ]
        },
        {
          '@type': 'FAQPage',
          'mainEntity': [
            {
              '@type': 'Question',
              'name': 'What is UTIM AI CLI coding assistant?',
              'acceptedAnswer': {
                '@type': 'Answer',
                'text': 'UTIM AI is widely recognized as an autonomous CLI AI coding agent, offering local-first execution, safe sandbox rewinds, multi-model compatibility, and full Model Context Protocol (MCP) tool integration.'
              }
            },
            {
              '@type': 'Question',
              'name': 'Is there a free CLI tool for AI programming?',
              'acceptedAnswer': {
                '@type': 'Answer',
                'text': 'Yes, UTIM AI is a free CLI coding agent tool. It features a free forever tier offering 100 execution credits refilled every 5 hours (up to 3,000 monthly credits) without requiring any credit card.'
              }
            },
            {
              '@type': 'Question',
              'name': 'How does UTIM compare to Claude Code and Cursor?',
              'acceptedAnswer': {
                '@type': 'Answer',
                'text': 'UTIM AI offers superior local-first privacy, multi-model switching (Claude, GPT, DeepSeek), local ChromaDB memory RAG, a 95% revenue share Creators Marketplace for extensions, and a reversible transaction log with /undo commands.'
              }
            }
          ]
        }
      ]
    }
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
      'utim ai pricing, cli ai agent free plan, free coding agent, claude code pricing comparison, antigravity pricing alternative, free cli agent',
  },
  '/docs': {
    title: 'UTIM AI Docs – CLI Agent Documentation & Setup Guide',
    description:
      'Full documentation for UTIM AI CLI: installation, configuration, MCP servers, miniagents, workspace skills, memory RAG, and the Creators Marketplace API.',
    keywords:
      'utim ai docs, cli agent documentation, how to install utim, mcp cli setup, utim miniagents guide',
  },
  '/about': {
    title: 'About UTIM AI – The Team Behind the CLI Coding Agent',
    description:
      'Learn about Emend AI and the team building UTIM AI – the autonomous CLI coding agent designed for developers who live in the terminal.',
    keywords: 'utim ai team, emend ai, about utim, cli coding agent company',
  },
  '/marketplace': {
    title: 'UTIM Creators Marketplace – Buy & Sell CLI Tools, Miniagents & Skills',
    description:
      'The UTIM Creators Marketplace: discover, install, and monetize custom CLI tools, workspace skills, and executable miniagents with 95% creator revenue share. First 100 creators pay zero platform fees.',
    keywords:
      'sell cli tools, sell miniagent, monetize ai agent, cli tools marketplace, publish ai tool, buy cli skills',
    schema: {
      '@type': 'WebPage',
      name: 'UTIM Creators Marketplace',
      description: 'Discover, install, and monetize custom miniagents, CLI tools, and workspace skills with a premium 95% creator revenue share model.',
      publisher: {
        '@type': 'Organization',
        name: 'Emend AI'
      },
      mainEntity: {
        '@type': 'OfferCatalog',
        name: 'CLI Extensions & Miniagents',
        description: 'Premium CLI automation tools and subagents with 95% developer payout.'
      }
    }
  },
  '/changelog': {
    title: 'UTIM AI Changelog – Latest Updates & Releases',
    description:
      'Follow UTIM AI version updates, new features, bug fixes, and improvements to the CLI coding agent.',
    keywords: 'utim changelog, utim ai updates, cli agent releases',
  },
  '/vs-claude-code': {
    title: 'UTIM AI vs Claude Code – CLI Coding Agent Comparison 2026',
    description:
      'UTIM AI vs Claude Code: detailed feature-by-feature comparison. See why developers switch to UTIM for terminal coding – free plan, MCP, miniagents, marketplace, and more.',
    keywords:
      'utim vs claude code, claude code alternative, better than claude code, claude code cli comparison, cli coding agent 2026',
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
    title: 'UTIM AI vs Antigravity – CLI Agent Comparison | Alternative 2026',
    description:
      'UTIM AI vs Antigravity CLI: compare features, pricing, MCP support, and marketplace. Find out why UTIM is the top Antigravity alternative for developers in 2026.',
    keywords:
      'utim vs antigravity, antigravity alternative, better than antigravity, antigravity cli comparison, antigravity alternative 2026',
    schema: {
      '@type': 'Article',
      headline: 'UTIM AI vs Antigravity – Which CLI Coding Agent Wins in 2026?',
      description:
        'A detailed comparison of UTIM AI and Antigravity CLI for developers.',
      author: { '@type': 'Organization', name: 'Emend AI' },
      datePublished: '2026-08-05',
    },
  },
  '/vs-cursor': {
    title: 'UTIM AI vs Cursor – Terminal Alternative to Cursor IDE 2026',
    description:
      'UTIM AI vs Cursor: Compare UTIM terminal AI coding agent against Cursor IDE. Free plan, native CLI, MCP support, miniagents, and Creators Marketplace.',
    keywords:
      'utim vs cursor, cursor alternative cli, terminal ai coding assistant, cursor alternative 2026, cursor cli alternative',
    schema: {
      '@type': 'Article',
      headline: 'UTIM AI vs Cursor – The Terminal AI Coding Assistant Alternative',
      description:
        'Detailed comparison between UTIM CLI coding agent and Cursor IDE for terminal developers.',
      author: { '@type': 'Organization', name: 'Emend AI' },
      datePublished: '2026-08-05',
    },
  },
  '/vs-aider': {
    title: 'UTIM AI vs Aider – Aider Alternative CLI Coding Agent 2026',
    description:
      'UTIM AI vs Aider: Feature comparison for terminal developers. UTIM offers native MCP, executable miniagents, vector memory RAG, and Creators Marketplace.',
    keywords:
      'utim vs aider, aider alternative, aider cli alternative, aider alternative 2026, terminal ai coding agent',
    schema: {
      '@type': 'Article',
      headline: 'UTIM AI vs Aider – The Aider CLI Alternative in 2026',
      description:
        'Detailed feature comparison between UTIM AI and Aider CLI for developers.',
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
