import React from 'react';
import { Link } from 'react-router-dom';
import ScrollytellingHeaderNav from '../components/ScrollytellingHeaderNav';
import DeveloperWorkbenchHero from '../components/DeveloperWorkbenchHero';
import TimeTravelRewindVisualizer from '../components/TimeTravelRewindVisualizer';
import ArchitectureFlowSection from '../components/ArchitectureFlowSection';
import SubagentSwarmVisualizer from '../components/SubagentSwarmVisualizer';
import SlashCommandMatrix from '../components/SlashCommandMatrix';
import PlatformAvailabilitySection from '../components/PlatformAvailabilitySection';
import InteractiveFaq from '../components/InteractiveFaq';
import SupportCommunitySection from '../components/SupportCommunitySection';
import ScrollytellingFooter from '../components/ScrollytellingFooter';
import SEOHead from '../components/SEOHead';
import { 
  Sparkles, ArrowRight, Cpu, Database, 
  Layers, Check, Terminal, Shield, Zap, 
  ShoppingBag, BookOpen, History, Gift,
  ExternalLink, ChevronRight 
} from 'lucide-react';
import { motion, useScroll, useSpring } from 'framer-motion';
import '../components/ScrollytellingMain.css';

export default function HomePage() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 400,
    damping: 30,
    restDelta: 0.001
  });

  return (
    <div className="st-page-root" style={{ position: 'relative' }}>
      <SEOHead
        title="UTIM AI — Autonomous Terminal Developer Agent"
        description="UTIM AI is the local-first autonomous developer agent for terminal-based software engineering. You prompt, it plans, tests, and builds."
        canonical="https://utim.dev/"
      />

      {/* Top Fast-Paced Scroll Progress Indicator */}
      <motion.div
        style={{
          scaleX,
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          height: 3,
          background: 'var(--accent-brand)',
          transformOrigin: '0%',
          zIndex: 9999
        }}
      />
      
      {/* 1. Global Navigation Bar with Home Link & Auth Profile */}
      <ScrollytellingHeaderNav />

      {/* 2. Dual-Workbench Developer Hero with Live Diffs */}
      <DeveloperWorkbenchHero />

      {/* 3. Cross-Platform Availability (Windows, Mac, Termux Android) */}
      <PlatformAvailabilitySection />

      {/* 4. Interactive Time-Travel Rewind Timeline & AST State Visualizer */}
      <TimeTravelRewindVisualizer />

      {/* 5. Interactive System Architecture Pipeline */}
      <ArchitectureFlowSection />

      {/* 6. Autonomous Subagent Swarm Visualizer */}
      <SubagentSwarmVisualizer />

      {/* 7. Keyboard-First Slash Command HUD */}
      <SlashCommandMatrix />

      {/* 7. Multi-Page Feature & Ecosystem Hub */}
      <section style={{ padding: '80px 24px', background: '#FFFFFF', borderTop: '1px solid var(--border-cream)', borderBottom: '1px solid var(--border-cream)' }}>
        <div className="st-container">
          <motion.div 
            initial={{ opacity: 0, y: 22 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ duration: 0.38, ease: [0.16, 1, 0.3, 1] }}
            className="st-section-header" 
            style={{ marginBottom: 40 }}
          >
            <div className="st-hero-badge">
              Explore the platform
            </div>
            <h2 className="st-section-title">
              Built Across Dedicated Developer Hubs
            </h2>
            <p className="st-section-subtitle">
              Explore deep documentation, live miniagent marketplaces, transparent pricing, and model benchmarks.
            </p>
          </motion.div>

          <div className="st-hub-grid">
            
            {/* Hub Card: Features & Models — featured dark panel */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ duration: 0.35, delay: 0.04 }}
              whileHover={{ y: -4, transition: { duration: 0.15 } }}
              className="st-hub-card-large"
              style={{
                background: 'var(--accent-black)',
                border: '1px solid var(--accent-black)',
                borderRadius: '22px 22px 10px 22px',
                padding: '28px 30px 24px 30px',
                display: 'flex',
                flexDirection: 'column'
              }}
            >
              <div style={{ width: 42, height: 42, borderRadius: 12, background: 'var(--accent-brand)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 18 }}>
                <Zap size={20} color="#FFFFFF" />
              </div>
              <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(1.45rem, 2.2vw, 1.9rem)', fontWeight: 600, lineHeight: 1.15, marginBottom: 10, color: '#FFFFFF' }}>
                Ten core capabilities, one command
              </h3>
              <p style={{ fontSize: 14, color: 'rgba(255, 255, 255, 0.7)', lineHeight: 1.7, marginBottom: 24, flex: 1, maxWidth: 520 }}>
                The full feature matrix, ChromaDB semantic memory, and a catalog of 11 free and premium models — all reachable from a single binary.
              </p>
              <Link to="/features" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 13.5, fontWeight: 600, color: '#F3E3D8', textDecoration: 'none' }}>
                View the feature matrix <ArrowRight size={14} />
              </Link>
            </motion.div>

            {/* Hub Card: Pricing & Credits */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ duration: 0.35, delay: 0.08 }}
              whileHover={{ y: -4, transition: { duration: 0.15 } }}
              className="st-hub-card-small"
              style={{
                background: '#FFFFFF',
                border: '1px solid var(--border-cream)',
                borderRadius: '10px 22px 22px 10px',
                padding: '24px 26px',
                display: 'flex',
                flexDirection: 'column'
              }}
            >
              <div style={{ width: 40, height: 40, borderRadius: 10, background: 'var(--bg-cream-pill)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16, border: '1px solid var(--border-cream)' }}>
                <Shield size={20} color="var(--text-primary)" />
              </div>
              <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.4rem', fontWeight: 600, lineHeight: 1.2, marginBottom: 10, color: 'var(--text-primary)' }}>
                Transparent pricing, five plans
              </h3>
              <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: 18, flex: 1 }}>
                From a free tier with 1,000 credits to Ultimate at $100 — no metered surprises, no lock-in.
              </p>
              <Link to="/pricing" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 13.5, fontWeight: 600, color: 'var(--accent-brand)', textDecoration: 'none' }}>
                Compare pricing plans <ArrowRight size={14} />
              </Link>
            </motion.div>

            {/* Hub Card: Documentation */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ duration: 0.35, delay: 0.12 }}
              whileHover={{ y: -4, transition: { duration: 0.15 } }}
              className="st-hub-card-small"
              style={{
                background: 'var(--bg-cream-alt)',
                border: '1px solid var(--border-cream)',
                borderRadius: '22px 10px 10px 22px',
                padding: '24px 26px',
                display: 'flex',
                flexDirection: 'column'
              }}
            >
              <div style={{ width: 40, height: 40, borderRadius: 10, background: '#FFFFFF', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16, border: '1px solid var(--border-cream)' }}>
                <BookOpen size={20} color="var(--text-primary)" />
              </div>
              <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.4rem', fontWeight: 600, lineHeight: 1.2, marginBottom: 10, color: 'var(--text-primary)' }}>
                A complete operating manual
              </h3>
              <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: 18, flex: 1 }}>
                Guides on configuration, keyboard commands, MCP stdio/SSE server setup, and prompt rules.
              </p>
              <Link to="/docs" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 13.5, fontWeight: 600, color: 'var(--accent-brand)', textDecoration: 'none' }}>
                Read the documentation <ArrowRight size={14} />
              </Link>
            </motion.div>

            {/* Hub Card: Marketplace */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ duration: 0.35, delay: 0.16 }}
              whileHover={{ y: -4, transition: { duration: 0.15 } }}
              className="st-hub-card-large"
              style={{
                background: '#FFFFFF',
                border: '1px solid var(--border-cream)',
                borderRadius: '10px 10px 22px 22px',
                padding: '24px 28px',
                display: 'flex',
                flexDirection: 'column',
                borderTop: '3px solid var(--accent-brand)'
              }}
            >
              <div style={{ width: 40, height: 40, borderRadius: 10, background: 'var(--accent-brand-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
                <ShoppingBag size={20} color="var(--accent-brand)" />
              </div>
              <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.5rem', fontWeight: 600, lineHeight: 1.15, marginBottom: 10, color: 'var(--text-primary)' }}>
                Miniagent marketplace, 95% revenue share
              </h3>
              <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: 18, flex: 1, maxWidth: 520 }}>
                Discover community-built tools, or publish your own miniagents and keep 95% of what they earn.
              </p>
              <Link to="/marketplace" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 13.5, fontWeight: 600, color: 'var(--accent-brand)', textDecoration: 'none' }}>
                Visit the marketplace <ArrowRight size={14} />
              </Link>
            </motion.div>

          </div>
        </div>
      </section>

      {/* 8. Honest Architecture Comparison Matrix */}
      <section style={{ padding: '75px 24px 80px 24px', background: 'var(--bg-cream-alt)', borderBottom: '1px solid var(--border-cream)' }}>
        <div className="st-container">
          <motion.div 
            initial={{ opacity: 0, y: 22 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ duration: 0.38, ease: [0.16, 1, 0.3, 1] }}
            className="st-section-header" 
            style={{ marginBottom: 36 }}
          >
            <div className="st-hero-badge">
              Honest architecture comparison
            </div>
            <h2 className="st-section-title">
              Architectural Differences
            </h2>
            <p className="st-section-subtitle">
              How UTIM AI compares with proprietary cloud IDEs and single-vendor CLI tools.
            </p>
          </motion.div>

          <motion.div 
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            whileInView={{ opacity: 1, y: 0, scale: 1 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ duration: 0.42, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
            className="st-comparison-card" 
            style={{ marginBottom: 32 }}
          >
            <div className="st-table-wrapper">
              <table className="st-comparison-table">
                <thead>
                  <tr>
                    <th style={{ width: '40%' }}>Capability</th>
                    <th className="st-col-utim" style={{ textAlign: 'center' }}>UTIM AI CLI</th>
                    <th style={{ textAlign: 'center' }}>Claude Code</th>
                    <th style={{ textAlign: 'center' }}>Cursor CLI</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="st-row-feature">100% Terminal Native (Zero IDE Lock-in)</td>
                    <td className="st-row-utim"><Check className="st-check-icon" size={18} /></td>
                    <td style={{ textAlign: 'center' }}><Check className="st-check-icon-gray" size={18} /></td>
                    <td style={{ textAlign: 'center' }}>❌</td>
                  </tr>
                  <tr>
                    <td className="st-row-feature">Local ChromaDB Semantic Vector Memory</td>
                    <td className="st-row-utim"><Check className="st-check-icon" size={18} /></td>
                    <td style={{ textAlign: 'center' }}>❌</td>
                    <td style={{ textAlign: 'center' }}>❌</td>
                  </tr>
                  <tr>
                    <td className="st-row-feature">Creators Miniagent Marketplace (80% Rev Share)</td>
                    <td className="st-row-utim"><Check className="st-check-icon" size={18} /></td>
                    <td style={{ textAlign: 'center' }}>❌</td>
                    <td style={{ textAlign: 'center' }}>❌</td>
                  </tr>
                  <tr>
                    <td className="st-row-feature">Reversible History Snapshots (/undo, /rewind)</td>
                    <td className="st-row-utim"><Check className="st-check-icon" size={18} /></td>
                    <td style={{ textAlign: 'center' }}>❌</td>
                    <td style={{ textAlign: 'center' }}>❌</td>
                  </tr>
                  <tr>
                    <td className="st-row-feature">Full MCP Tool Integration (Stdio & SSE)</td>
                    <td className="st-row-utim"><Check className="st-check-icon" size={18} /></td>
                    <td style={{ textAlign: 'center' }}>⚠️ Limited</td>
                    <td style={{ textAlign: 'center' }}>❌</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </motion.div>

          <div style={{ display: 'flex', justifyContent: 'center', gap: 16, flexWrap: 'wrap' }}>
            <Link 
              to="/vs-claude-code" 
              className="st-tag-item" 
              style={{ textDecoration: 'none', padding: '8px 18px', fontSize: 13.5 }}
            >
              UTIM vs Claude Code →
            </Link>
            <Link 
              to="/vs-cursor" 
              className="st-tag-item" 
              style={{ textDecoration: 'none', padding: '8px 18px', fontSize: 13.5 }}
            >
              UTIM vs Cursor CLI →
            </Link>
            <Link 
              to="/vs-antigravity" 
              className="st-tag-item" 
              style={{ textDecoration: 'none', padding: '8px 18px', fontSize: 13.5 }}
            >
              UTIM vs Antigravity →
            </Link>
            <Link 
              to="/vs-aider" 
              className="st-tag-item" 
              style={{ textDecoration: 'none', padding: '8px 18px', fontSize: 13.5 }}
            >
              UTIM vs Aider →
            </Link>
          </div>
        </div>
      </section>

      {/* 9. Developer FAQ Accordion */}
      <InteractiveFaq />

      {/* 10. Community & Support */}
      <SupportCommunitySection />

      {/* 11. Global Footer */}
      <ScrollytellingFooter />
    </div>
  );
}
