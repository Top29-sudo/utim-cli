import React from 'react';
import ScrollytellingHeaderNav from '../components/ScrollytellingHeaderNav';
import ScrollytellingFooter from '../components/ScrollytellingFooter';
import SEOHead from '../components/SEOHead';
import { ShoppingBag, Sparkles, DollarSign, Bot, Download, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import '../components/ScrollytellingMain.css';

export default function MarketplacePage() {
  const miniagents = [
    {
      title: "Playwright Full-Stack QA Agent",
      author: "@alex_dev",
      price: "Free",
      downloads: "3.4k",
      desc: "End-to-end autonomous browser testing, screenshot diff analysis, and cross-browser regression test generator.",
      tags: ["Testing", "Playwright", "Browser"],
      span: "st-bento-span-2"
    },
    {
      title: "FastAPI & SQLAlchemy Scaffolder",
      author: "@backend_ninja",
      price: "$4.99",
      downloads: "1.8k",
      desc: "Bootstraps production-grade REST APIs with Alembic migrations, JWT authentication, and Docker Compose in seconds.",
      tags: ["FastAPI", "Python", "Docker"],
      span: ""
    },
    {
      title: "Next.js 15 Tailwind UI Designer",
      author: "@craft_ui",
      price: "$9.99",
      downloads: "2.9k",
      desc: "Generates modern React Server Components, responsive glassmorphism UI layouts, and accessible Radix components.",
      tags: ["Next.js", "React", "Tailwind"],
      span: ""
    },
    {
      title: "ChromaDB RAG Document Ingester",
      author: "@rag_expert",
      price: "$2.99",
      downloads: "940",
      desc: "Parses PDF, Markdown, and source code files, chunking and embedding them directly into local vector memory.",
      tags: ["ChromaDB", "RAG", "Embeddings"],
      span: "st-bento-span-2"
    }
  ];

  return (
    <div className="st-page-root">
      <SEOHead
        title="Creators Miniagent Marketplace — UTIM AI CLI"
        description="Discover, install, and sell custom miniagents for UTIM CLI. Creators keep 95% revenue share on every sale."
        canonical="https://utim.dev/marketplace"
      />
      <ScrollytellingHeaderNav />

      {/* Hero Header */}
      <div style={{ padding: '80px 24px 40px 24px', textAlign: 'center' }}>
        <div className="st-container">
          <div className="st-hero-badge">
            <ShoppingBag size={14} /> CREATORS ECOSYSTEM
          </div>
          <h1 className="st-section-title" style={{ fontSize: 'clamp(2.4rem, 4.5vw, 3.6rem)' }}>
            Creators Miniagent Marketplace
          </h1>
          <p className="st-section-subtitle" style={{ maxWidth: 740, margin: '0 auto 32px auto' }}>
            Build specialized subagents, tools, and workflows for UTIM CLI. Publish to thousands of developers and earn <strong>95% revenue share</strong> on every sale.
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 16 }}>
            <Link to="/auth" className="st-nav-primary-btn" style={{ padding: '12px 26px', fontSize: 15 }}>
              Publish a Miniagent
            </Link>
          </div>
        </div>
      </div>

      {/* Miniagents Grid */}
      <div className="st-container" style={{ paddingBottom: 100 }}>
        <div className="st-bento-grid">
          {miniagents.map((agent, idx) => (
            <div key={idx} className={`st-bento-card ${agent.span}`}>
              <div className="st-card-top-row">
                <div className="st-card-icon-box">
                  <Bot size={24} />
                </div>
                <span style={{ fontSize: '13.5px', fontWeight: 800, color: 'var(--text-primary)', background: 'var(--bg-cream-pill)', padding: '5px 14px', borderRadius: 100, border: '1px solid var(--border-cream)' }}>
                  {agent.price}
                </span>
              </div>
              <h3 className="st-card-title">{agent.title}</h3>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: 14 }}>by {agent.author} • {agent.downloads} downloads</p>
              <p className="st-card-desc">{agent.desc}</p>
              <div className="st-tags-list">
                {agent.tags.map((tag, tIdx) => (
                  <span key={tIdx} className="st-tag-item">{tag}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <ScrollytellingFooter />
    </div>
  );
}
