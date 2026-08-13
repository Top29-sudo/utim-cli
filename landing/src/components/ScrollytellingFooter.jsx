import React from 'react';
import { Link } from 'react-router-dom';

export default function ScrollytellingFooter() {
  return (
    <footer className="st-footer">
      <div className="st-footer-inner">
        <div className="st-footer-grid">
          {/* Col 1: Brand */}
          <div className="st-footer-brand">
            <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <img src="/logo.png" alt="UTIM AI logo" className="st-brand-logo-img" />
              <span style={{ fontFamily: 'var(--font-display)', fontSize: 19, fontWeight: 600, letterSpacing: '-0.01em', color: 'var(--text-primary)' }}>UTIM AI</span>
            </Link>
            <p>
              Autonomous terminal AI agent engineered for developers. 
              You Think It, I Make It.
            </p>
          </div>

          {/* Col 2: Product */}
          <div className="st-footer-col">
            <h4>Product</h4>
            <ul className="st-footer-links">
              <li><Link to="/features">Features</Link></li>
              <li><Link to="/pricing">Pricing Plans</Link></li>
              <li><Link to="/docs">Documentation</Link></li>
              <li><Link to="/marketplace">Miniagent Marketplace</Link></li>
              <li><Link to="/changelog">Changelog</Link></li>
              <li><Link to="/referral">Referral Program</Link></li>
            </ul>
          </div>

          {/* Col 3: Comparisons */}
          <div className="st-footer-col">
            <h4>Comparisons</h4>
            <ul className="st-footer-links">
              <li><Link to="/vs-claude-code">vs Claude Code</Link></li>
              <li><Link to="/vs-cursor">vs Cursor CLI</Link></li>
              <li><Link to="/vs-antigravity">vs Antigravity</Link></li>
              <li><Link to="/vs-aider">vs Aider</Link></li>
            </ul>
          </div>

          {/* Col 4: Legal & Support */}
          <div className="st-footer-col">
            <h4>Company & Legal</h4>
            <ul className="st-footer-links">
              <li><Link to="/about">About UTIM & Team</Link></li>
              <li><Link to="/support">Support Channels</Link></li>
              <li><a href="https://discord.com/invite/wGB7M8pMEy" target="_blank" rel="noreferrer">Discord Server</a></li>
              <li><Link to="/terms">Terms of Service</Link></li>
              <li><Link to="/privacy">Privacy Policy</Link></li>
              <li><Link to="/refund">Refund Policy</Link></li>
              <li><Link to="/license">License</Link></li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="st-footer-bottom">
          <div>
            © {new Date().getFullYear()} UTIM AI. Developed by Emendai. All rights reserved.
          </div>
          <div style={{ display: 'flex', gap: 20 }}>
            <span>Local-First Architecture</span>
            <span>•</span>
            <span>200+ MCP Servers</span>
            <span>•</span>
            <span>Zero IDE Dependencies</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
