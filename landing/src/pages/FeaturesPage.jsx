import React from 'react';
import { Link } from 'react-router-dom';
import ScrollytellingHeaderNav from '../components/ScrollytellingHeaderNav';
import BentoGridSection from '../components/BentoGridSection';
import ModelRegistryExplorer from '../components/ModelRegistryExplorer';
import ArchitectureFlowSection from '../components/ArchitectureFlowSection';
import ScrollytellingFooter from '../components/ScrollytellingFooter';
import SEOHead from '../components/SEOHead';
import { Sparkles, ArrowRight, Terminal, Shield, Cpu, Database, Layers } from 'lucide-react';
import { motion } from 'framer-motion';
import '../components/ScrollytellingMain.css';

export default function FeaturesPage() {
  return (
    <div className="st-page-root">
      <SEOHead
        title="Features & Capabilities — UTIM AI CLI"
        description="Explore the complete 10 core autonomous capabilities, vector memory RAG, MCP tools, and multi-model registry of UTIM AI CLI."
        canonical="https://utim.dev/features"
      />
      <ScrollytellingHeaderNav />

      {/* Page Hero Header */}
      <div style={{ padding: '70px 24px 30px 24px', textAlign: 'center', background: '#FFFFFF', borderBottom: '1px solid var(--border-cream)' }}>
        <div className="st-container">
          <motion.h1 
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.06, ease: [0.16, 1, 0.3, 1] }}
            className="st-section-title" 
            style={{ fontSize: 'clamp(2.4rem, 4.5vw, 3.8rem)', maxWidth: 880, margin: '0 auto 16px auto' }}
          >
            10 Autonomous Superpowers for Terminal Developers
          </motion.h1>

          <motion.p 
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.12, ease: [0.16, 1, 0.3, 1] }}
            className="st-section-subtitle" 
            style={{ maxWidth: 760, margin: '0 auto 28px auto' }}
          >
            From self-healing test loops and local ChromaDB semantic memory to native Model Context Protocol (MCP) integrations and multi-model hot swapping.
          </motion.p>

          <motion.div 
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.18, ease: [0.16, 1, 0.3, 1] }}
            style={{ display: 'flex', justifyContent: 'center', gap: 14, flexWrap: 'wrap' }}
          >
            <Link to="/auth?mode=signup" className="st-nav-primary-btn" style={{ padding: '11px 24px', fontSize: 14.5 }}>
              <span>Get Started Free (1,000 Credits)</span>
              <ArrowRight size={15} />
            </Link>
            <Link to="/docs" className="st-btn-secondary" style={{ padding: '11px 22px', fontSize: 14.5, borderRadius: 10, display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <Terminal size={16} /> Read Documentation
            </Link>
          </motion.div>
        </div>
      </div>

      {/* 1. Complete 10-Feature Bento Grid Matrix */}
      <BentoGridSection />

      {/* 2. Interactive Local-First Architecture Flow */}
      <ArchitectureFlowSection />

      {/* 3. Live Model Registry & Token Explorer */}
      <ModelRegistryExplorer />

      {/* Bottom CTA Banner */}
      <section style={{ padding: '70px 24px', background: 'var(--accent-black)', color: '#FFFFFF', textAlign: 'center' }}>
        <div className="st-container" style={{ maxWidth: 780 }}>
          <h2 style={{ fontSize: 'clamp(2rem, 3.5vw, 2.8rem)', fontWeight: 850, marginBottom: 16, letterSpacing: '-0.03em', color: '#FFFFFF' }}>
            Ready to experience terminal autonomy?
          </h2>
          <p style={{ fontSize: '1.1rem', color: '#94a3b8', lineHeight: 1.65, marginBottom: 28 }}>
            Install UTIM CLI with one command and start coding with 1,000 free monthly credits.
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 16, flexWrap: 'wrap' }}>
            <Link to="/auth?mode=signup" className="st-nav-primary-btn" style={{ background: '#FFFFFF', color: '#121214', padding: '12px 28px', fontSize: 15 }}>
              <span>Create Free Account</span>
              <ArrowRight size={16} color="#121214" />
            </Link>
            <Link to="/pricing" className="st-btn-secondary" style={{ background: 'rgba(255,255,255,0.1)', color: '#FFFFFF', border: '1px solid rgba(255,255,255,0.2)', padding: '12px 24px', fontSize: 15, borderRadius: 10 }}>
              <span>View Pricing Plans</span>
            </Link>
          </div>
        </div>
      </section>

      <ScrollytellingFooter />
    </div>
  );
}
