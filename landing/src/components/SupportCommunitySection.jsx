import React from 'react';
import { MessageSquare, Mail, Users, Gift, Sparkles, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function SupportCommunitySection() {
  return (
    <section className="st-community-section" id="community">
      <div className="st-container">
        {/* Section Header */}
        <div className="st-section-header">
          <div className="st-hero-badge">
            <Users size={14} /> Community & support
          </div>
          <h2 className="st-section-title">
            Built for Builders, Supported by Engineers
          </h2>
          <p className="st-section-subtitle">
            Join thousands of developers using UTIM to build applications at the speed of thought.
          </p>
        </div>

        {/* 4 Community & Support Cards */}
        <div className="st-community-grid">
          {/* Card 1: Discord Community */}
          <a 
            href="https://discord.com/invite/wGB7M8pMEy" 
            target="_blank" 
            rel="noopener noreferrer"
            className="st-community-card"
          >
            <div className="st-card-icon-box" style={{ marginBottom: 16 }}>
              <MessageSquare size={22} />
            </div>
            <h3 className="st-card-title" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span>Discord Server</span>
              <ExternalLink size={16} color="var(--text-muted)" />
            </h3>
            <p className="st-card-desc">
              Join our community server to share CLI workflows, get help, test custom skills, and chat directly with other creators.
            </p>
            <span className="st-community-link-label">
              Join Discord Server →
            </span>
          </a>

          {/* Card 2: Direct Support */}
          <a 
            href="mailto:support@utim.dev"
            className="st-community-card"
          >
            <div className="st-card-icon-box" style={{ marginBottom: 16 }}>
              <Mail size={22} />
            </div>
            <h3 className="st-card-title">Direct Support</h3>
            <p className="st-card-desc">
              For enterprise inquiries, billing assistance, or dedicated account support, reach out to <code>support@utim.dev</code>.
            </p>
            <span className="st-community-link-label">
              Email Engineering Team →
            </span>
          </a>

          {/* Card 3: Referral Program */}
          <Link to="/referral" className="st-community-card">
            <div className="st-card-icon-box" style={{ marginBottom: 16 }}>
              <Gift size={22} />
            </div>
            <h3 className="st-card-title">Referral Program</h3>
            <p className="st-card-desc">
              Share your personal tracking link. When friends sign up and subscribe, both receive bonus credits automatically applied to billing.
            </p>
            <span className="st-community-link-label">
              View Referral Dashboard →
            </span>
          </Link>

          {/* Card 4: About Emendai */}
          <div className="st-community-card">
            <div className="st-card-icon-box" style={{ marginBottom: 16 }}>
              <Sparkles size={22} />
            </div>
            <h3 className="st-card-title">Developed by Emendai</h3>
            <p className="st-card-desc">
              Our mission is to automate repetitive software engineering tasks, enabling developers to build complex applications at the speed of thought.
            </p>
            <span className="st-community-meta">
              UTIM v2.1.3 Production Release
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
