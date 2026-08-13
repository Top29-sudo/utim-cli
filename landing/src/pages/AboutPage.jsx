import React from 'react';
import ScrollytellingHeaderNav from '../components/ScrollytellingHeaderNav';
import ScrollytellingFooter from '../components/ScrollytellingFooter';
import SEOHead from '../components/SEOHead';
import { Sparkles, Users, Target, Terminal } from 'lucide-react';
import { Link } from 'react-router-dom';
import '../components/ScrollytellingMain.css';

export default function AboutPage() {
  return (
    <div className="st-page-root">
      <SEOHead
        title="About UTIM & Team — Emendai"
        description="UTIM (You Think It, I Make It) is designed to bridge the gap between human design ideas and production-grade code implementation."
        canonical="https://utim.dev/about"
      />
      <ScrollytellingHeaderNav />

      <div style={{ padding: '70px 24px', maxWidth: 840, margin: '0 auto' }}>
        <h1 className="st-section-title" style={{ fontSize: 'clamp(2.4rem, 4.5vw, 3.6rem)', marginBottom: 20 }}>
          You Think It, I Make It.
        </h1>
        
        <p style={{ fontSize: '1.2rem', color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: 32 }}>
          UTIM (You Think It, I Make It) is designed to bridge the gap between human design ideas and production-grade code implementation.
        </p>

        <div className="st-doc-card" style={{ marginBottom: 32 }}>
          <h2 className="st-doc-card-title">
            <Users size={22} /> Developed by Emendai
          </h2>
          <p style={{ fontSize: '1rem', color: 'var(--text-body)', lineHeight: 1.7 }}>
            Our mission is to automate repetitive software engineering tasks, enabling developers to build complex applications at the speed of thought. 
            We believe that the future of coding is autonomous, high-agency, and terminal-native.
          </p>
        </div>

        <div className="st-doc-card" style={{ marginBottom: 32 }}>
          <h2 className="st-doc-card-title">
            <Target size={22} /> Core Values
          </h2>
          <ul style={{ listStyle: 'none', fontSize: '0.96rem', color: 'var(--text-body)', lineHeight: 1.8 }}>
            <li>✔ <strong>Local-First Privacy:</strong> Your source code stays on your machine. UTIM executes directly in your local environment.</li>
            <li>✔ <strong>Zero Lock-in:</strong> Connect any provider key (BYOK), any MCP server, and use open models without restrictions.</li>
            <li>✔ <strong>Reversibility & Safety:</strong> Every modification is diffed and snapshotted with <code>/undo</code> and <code>/rewind</code>.</li>
            <li>✔ <strong>Creators Economy:</strong> Creators build custom miniagents and earn 95% revenue share on the UTIM Marketplace.</li>
          </ul>
        </div>

        <div style={{ display: 'flex', gap: 14, marginTop: 40 }}>
          <Link to="/auth" className="st-nav-primary-btn" style={{ padding: '10px 22px' }}>
            Get Started Free
          </Link>
          <Link to="/features" className="st-btn-secondary" style={{ padding: '10px 22px', borderRadius: 8 }}>
            Explore Features →
          </Link>
        </div>
      </div>

      <ScrollytellingFooter />
    </div>
  );
}
