import React from 'react';
import ScrollytellingHeaderNav from '../components/ScrollytellingHeaderNav';
import ScrollytellingFooter from '../components/ScrollytellingFooter';
import SEOHead from '../components/SEOHead';
import { MessageSquare, Mail, HelpCircle, ExternalLink, Sparkles } from 'lucide-react';
import '../components/ScrollytellingMain.css';

export default function SupportPage() {
  return (
    <div className="st-page-root">
      <SEOHead
        title="Support & Community — UTIM AI CLI"
        description="Official support channels, Discord community, and direct assistance for UTIM AI CLI."
        canonical="https://utim.dev/support"
      />
      <ScrollytellingHeaderNav />

      <div style={{ padding: '70px 24px', maxWidth: 840, margin: '0 auto' }}>
        <div className="st-hero-badge">
          <HelpCircle size={14} /> SUPPORT & CHANNELS
        </div>
        <h1 className="st-section-title" style={{ fontSize: 'clamp(2.4rem, 4.5vw, 3.6rem)', marginBottom: 20 }}>
          UTIM CLI Support Channels
        </h1>
        
        <p style={{ fontSize: '1.15rem', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 36 }}>
          Need assistance with installation, custom skills, Model Context Protocol servers, or account billing? Reach out to our engineering team.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(280px, 100%), 1fr))', gap: 24, marginBottom: 36 }}>
          {/* Discord */}
          <div className="st-doc-card">
            <h2 className="st-doc-card-title">
              <MessageSquare size={20} /> Discord Community
            </h2>
            <p style={{ fontSize: '0.94rem', color: 'var(--text-body)', lineHeight: 1.6, marginBottom: 16 }}>
              Join our server for community support, sharing builds, and chat with creators and core maintainers.
            </p>
            <a 
              href="https://discord.com/invite/wGB7M8pMEy"
              target="_blank"
              rel="noopener noreferrer"
              className="st-nav-primary-btn"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', fontSize: 13 }}
            >
              <span>Join Discord</span> <ExternalLink size={14} />
            </a>
          </div>

          {/* Email */}
          <div className="st-doc-card">
            <h2 className="st-doc-card-title">
              <Mail size={20} /> Direct Support Email
            </h2>
            <p style={{ fontSize: '0.94rem', color: 'var(--text-body)', lineHeight: 1.6, marginBottom: 16 }}>
              For enterprise queries, billing assistance, or sensitive account issues:
            </p>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: 13, color: 'var(--text-primary)', marginBottom: 14 }}>
              <div>• uthinkimake.official@gmail.com</div>
              <div>• support@utim.dev</div>
            </div>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Response SLA: Within 24–48 business hours.
            </p>
          </div>
        </div>

        <div className="st-doc-card">
          <h2 className="st-doc-card-title">
            <Sparkles size={20} /> Common Troubleshooting
          </h2>
          <ul style={{ listStyle: 'none', fontSize: '0.92rem', color: 'var(--text-body)', lineHeight: 1.8 }}>
            <li>• <strong>Command not found:</strong> Ensure your npm global bin directory is in your system <code>PATH</code>, or use <code>pip install utim</code>.</li>
            <li>• <strong>Login synchronization:</strong> Run <code>utim login</code> or inside TUI type <code>/login</code> to refresh credentials.</li>
            <li>• <strong>BYOK setup:</strong> Open model selector with <code>/model</code> and enter custom OpenAI-compatible baseUrl and apiKey.</li>
          </ul>
        </div>
      </div>

      <ScrollytellingFooter />
    </div>
  );
}
