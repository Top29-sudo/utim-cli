import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { 
  Terminal, Copy, Check, Play, ArrowRight, 
  RotateCcw, Sparkles, FileCode, CheckCircle2, 
  Layers, Shield, Cpu, ChevronRight, CornerDownLeft, Zap,
  Activity, Clock, DollarSign
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const WORKBENCH_PREVIEWS = {
  stripe: {
    id: 'stripe',
    name: 'Stripe Webhooks & Idempotency',
    prompt: 'Implement a Stripe webhook endpoint in Express with idempotency keys, DB transactions, and signature verification.',
    model: 'anthropic/claude-sonnet-4.6',
    tokens: '1,420 tokens ($0.004)',
    latency: '1.8s',
    terminalSteps: [
      { type: 'step', text: '1/4 [ANALYZE] Found Express router in `src/server.ts` & Prisma schema in `prisma/schema.prisma`' },
      { type: 'tool', text: '→ tool_call: replace_file_content `prisma/schema.prisma` (+IdempotencyRecord model)' },
      { type: 'tool', text: '→ tool_call: write_to_file `src/middleware/stripeWebhook.ts`' },
      { type: 'step', text: '2/4 [EXECUTE] Running `npx prisma db push && npm test`' },
      { type: 'success', text: '✓ 12 unit tests passing. Signature replay protection verified.' },
      { type: 'done', text: '⚡ Task finished in 1.8s. 0 manual edits needed.' }
    ],
    file: 'src/middleware/stripeWebhook.ts',
    diff: [
      { type: 'header', text: '@@ -0,0 +1,18 @@' },
      { type: 'add', text: '+ import { Request, Response } from "express";' },
      { type: 'add', text: '+ import stripe from "../lib/stripe";' },
      { type: 'add', text: '+ import { prisma } from "../db/client";' },
      { type: 'add', text: '+ ' },
      { type: 'add', text: '+ export async function handleStripeWebhook(req: Request, res: Response) {' },
      { type: 'add', text: '+   const sig = req.headers["stripe-signature"] as string;' },
      { type: 'add', text: '+   const event = stripe.webhooks.constructEvent(req.body, sig, process.env.STRIPE_SECRET! );' },
      { type: 'add', text: '+   ' },
      { type: 'add', text: '+   // Idempotent database record check' },
      { type: 'add', text: '+   const existing = await prisma.webhookEvent.findUnique({ where: { eventId: event.id } });' },
      { type: 'add', text: '+   if (existing) return res.status(200).json({ received: true, cached: true });' },
      { type: 'add', text: '+   ' },
      { type: 'add', text: '+   await prisma.webhookEvent.create({ data: { eventId: event.id, status: "PROCESSED" } });' },
      { type: 'add', text: '+   return res.status(200).json({ received: true });' },
      { type: 'add', text: '+ }' },
    ]
  },
  rag: {
    id: 'rag',
    name: 'ChromaDB Local Vector Memory',
    prompt: 'Query ChromaDB semantic memory for our repo authentication pattern and implement an API key rate limiter.',
    model: 'deepseek/deepseek-r1',
    tokens: '2,180 tokens ($0.002)',
    latency: '2.1s',
    terminalSteps: [
      { type: 'step', text: '1/3 [RAG] Querying local ChromaDB vector graph for `auth_pattern`...' },
      { type: 'tool', text: '→ Retrieved: Bearer JWT validation in `src/auth/jwt.ts` (0.96 cosine similarity)' },
      { type: 'tool', text: '→ tool_call: write_to_file `src/middleware/rateLimiter.ts`' },
      { type: 'step', text: '2/3 [TEST] Benchmarking rate limiter with 1,000 parallel mock requests' },
      { type: 'success', text: '✓ 429 Too Many Requests correctly returned at limit threshold.' },
      { type: 'done', text: '⚡ Rate limiter mounted across all `/api/v1/*` routes.' }
    ],
    file: 'src/middleware/rateLimiter.ts',
    diff: [
      { type: 'header', text: '@@ -0,0 +1,14 @@' },
      { type: 'add', text: '+ import rateLimit from "express-rate-limit";' },
      { type: 'add', text: '+ ' },
      { type: 'add', text: '+ export const apiLimiter = rateLimit({' },
      { type: 'add', text: '+   windowMs: 60 * 1000, // 1 minute' },
      { type: 'add', text: '+   max: 120, // 120 requests per minute per IP' },
      { type: 'add', text: '+   standardHeaders: true,' },
      { type: 'add', text: '+   legacyHeaders: false,' },
      { type: 'add', text: '+   message: { error: "Too many requests, please retry in 60s." }' },
      { type: 'add', text: '+ });' }
    ]
  },
  undo: {
    id: 'undo',
    name: 'Reversible /undo Rollback',
    prompt: 'utim /undo — Revert the last experimental refactor cleanly without git stash conflicts.',
    model: 'google/gemini-3.6-flash',
    tokens: '490 tokens (FREE)',
    latency: '0.4s',
    terminalSteps: [
      { type: 'step', text: '1/2 [SNAPSHOT] Inspecting atomic session checkpoint #14 (23:18:04)...' },
      { type: 'tool', text: '→ Restoring original `src/db/pool.ts` (reverted 38 line diff)' },
      { type: 'tool', text: '→ Removed temporary benchmark script `benchmark.js`' },
      { type: 'success', text: '✓ Workspace rolled back to clean state at 23:18:04.' },
      { type: 'done', text: '⚡ 0 git conflicts. Working tree completely clean.' }
    ],
    file: 'src/db/pool.ts',
    diff: [
      { type: 'header', text: '@@ -12,4 +12,4 @@' },
      { type: 'del', text: '- export const pool = new Pool({ max: 100, idleTimeoutMillis: 1000 });' },
      { type: 'add', text: '+ export const pool = new Pool({ max: 20, idleTimeoutMillis: 30000 });' },
      { type: 'normal', text: '  pool.on("error", (err) => console.error("Unexpected DB error", err));' }
    ]
  }
};

export default function DeveloperWorkbenchHero() {
  const [activeTab, setActiveTab] = useState('npm'); // 'npm' | 'pip'
  const [copied, setCopied] = useState(false);
  const [selectedPreview, setSelectedPreview] = useState('stripe');
  const [customPrompt, setCustomPrompt] = useState('');

  const preview = WORKBENCH_PREVIEWS[selectedPreview] || WORKBENCH_PREVIEWS.stripe;

  const installCommandsMap = {
    npm: 'npm install -g @emend-ai/utim',
    pip: 'pip install ".[full]"',
    powershell: 'iwr https://utim.dev/install.ps1 | iex',
    termux: 'pkg update -y && pkg install nodejs python -y && npm install -g @emend-ai/utim'
  };

  const installCommand = installCommandsMap[activeTab] || installCommandsMap.npm;

  const handleCopy = () => {
    navigator.clipboard.writeText(installCommand);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section className="st-hero-section" style={{ padding: '75px 24px 60px 24px', position: 'relative', overflow: 'hidden' }}>
      
      {/* Background Matrix Grid Pattern */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundImage: 'radial-gradient(rgba(18, 18, 20, 0.06) 1px, transparent 1px)',
        backgroundSize: '28px 28px',
        pointerEvents: 'none',
        zIndex: 0
      }} />

      {/* Ambient Spotlight */}
      <div style={{
        position: 'absolute',
        top: '5%',
        left: '50%',
        transform: 'translateX(-50%)',
        width: '900px',
        height: '450px',
        background: 'radial-gradient(circle at 50% 30%, rgba(2, 132, 199, 0.09) 0%, rgba(250, 248, 245, 0) 70%)',
        pointerEvents: 'none',
        zIndex: 0
      }} />

      <div className="st-container" style={{ position: 'relative', zIndex: 1 }}>
        
        {/* Top Minimalist Animated Pill */}
        <motion.div 
          initial={{ opacity: 0, scale: 0.92, y: -16 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          style={{ textAlign: 'center', marginBottom: 20 }}
        >
          <div className="st-hero-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: 10, padding: '0', background: 'transparent', border: 'none', borderRadius: 0, fontSize: 13, fontWeight: 600, boxShadow: 'none' }}>
            <span style={{ position: 'relative', display: 'flex', width: 8, height: 8 }}>
              <span style={{ position: 'absolute', width: '100%', height: '100%', borderRadius: '50%', background: 'var(--accent-brand)', opacity: 0.5, animation: 'ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite' }}></span>
              <span style={{ position: 'relative', display: 'inline-flex', width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-brand)' }}></span>
            </span>
            <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>UTIM CLI v2.1.3</span>
            <span style={{ color: 'var(--text-muted)' }}>·</span>
            <span style={{ color: 'var(--text-secondary)' }}>autonomous terminal coding agent</span>
          </div>
        </motion.div>

        {/* Hero Headline */}
        <motion.h1 
          initial={{ opacity: 0, y: 22 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.42, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 600,
            fontSize: 'clamp(1.85rem, 5.5vw, 4.5rem)',
            color: 'var(--text-primary)',
            textAlign: 'center',
            letterSpacing: '-0.022em',
            lineHeight: 1.08,
            maxWidth: 920,
            margin: '0 auto 22px auto',
            textWrap: 'balance'
          }}
        >
          Autonomous coding inside your terminal.
        </motion.h1>

        {/* Subtitle */}
        <motion.p 
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.42, delay: 0.16, ease: [0.16, 1, 0.3, 1] }}
          style={{
            fontSize: 'clamp(1.05rem, 2vw, 1.25rem)',
            color: 'var(--text-secondary)',
            textAlign: 'center',
            lineHeight: 1.7,
            maxWidth: 760,
            margin: '0 auto 36px auto',
            fontWeight: 400
          }}
        >
          You prompt. UTIM reads your repo, builds an execution plan, edits files across directories, runs tests, and snapshots changes for instantaneous <code>/undo</code> rollbacks.
        </motion.p>

        {/* Command Box & CTA Buttons */}
        <motion.div 
          initial={{ opacity: 0, y: 20, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.4, delay: 0.22, ease: [0.16, 1, 0.3, 1] }}
          style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, marginBottom: 44 }}
        >
          
          {/* Quick Install Pill with All Platform Options */}
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            background: '#FFFFFF',
            border: '1px solid var(--border-cream)',
            borderRadius: 12,
            padding: '6px 8px 6px 14px',
            boxShadow: 'var(--shadow-sm)',
            maxWidth: '100%',
            gap: 12,
            flexWrap: 'wrap',
            justifyContent: 'center',
            transition: 'border-color 0.2s ease, transform 0.2s ease'
          }}>
            {/* Tab switchers */}
            <div style={{ display: 'flex', gap: 4, background: 'var(--bg-cream)', padding: 3, borderRadius: 8, flexWrap: 'wrap' }}>
              {[
                { id: 'npm', label: 'npm' },
                { id: 'pip', label: 'pip' },
                { id: 'powershell', label: 'powershell' },
                { id: 'termux', label: 'termux' }
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    border: 'none',
                    background: activeTab === tab.id ? '#FFFFFF' : 'transparent',
                    color: activeTab === tab.id ? 'var(--text-primary)' : 'var(--text-muted)',
                    fontSize: 12,
                    fontWeight: 700,
                    padding: '4px 10px',
                    borderRadius: 6,
                    cursor: 'pointer',
                    boxShadow: activeTab === tab.id ? 'var(--shadow-xs)' : 'none',
                    transition: 'all 0.15s ease'
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Code string */}
            <code style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '13.5px',
              color: 'var(--text-primary)',
              fontWeight: 600,
              userSelect: 'all',
              maxWidth: 420,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}>
              {installCommand}
            </code>

            {/* Copy button */}
            <button
              onClick={handleCopy}
              style={{
                background: 'var(--accent-black)',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: 8,
                padding: '7px 14px',
                fontSize: 12.5,
                fontWeight: 700,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                transition: 'all 0.15s ease'
              }}
            >
              {copied ? <><Check size={13} color="#4ADE80" /> Copied</> : <><Copy size={13} /> Copy</>}
            </button>
          </div>

          {/* Action Links */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', justifyContent: 'center' }}>
            <Link to="/auth?mode=signup" className="st-nav-primary-btn" style={{ padding: '11px 24px', fontSize: 14.5 }}>
              <span>Get Started Free (1,000 Credits)</span>
              <ArrowRight size={16} />
            </Link>

            <Link to="/features" className="st-btn-secondary" style={{ padding: '10px 20px', borderRadius: 10, fontSize: 14.5 }}>
              <span>Explore 10 Capabilities</span>
            </Link>
          </div>
        </motion.div>

        {/* =========================================================================
            Dual-Workbench Interactive Live Simulator with Iridescent Border
            ========================================================================= */}
        <motion.div 
          initial={{ opacity: 0, y: 32, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.5, delay: 0.28, ease: [0.16, 1, 0.3, 1] }}
          style={{ maxWidth: 1100, margin: '0 auto' }}
        >
          
          {/* Scenario Selector & Model Specs */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {Object.values(WORKBENCH_PREVIEWS).map((p) => {
                const isSelected = p.id === selectedPreview;
                return (
                  <button
                    key={p.id}
                    onClick={() => setSelectedPreview(p.id)}
                    style={{
                      padding: '7px 16px',
                      borderRadius: 999,
                      fontSize: 12.5,
                      fontWeight: 750,
                      cursor: 'pointer',
                      border: isSelected ? '1px solid var(--accent-black)' : '1px solid var(--border-cream)',
                      background: isSelected ? 'var(--accent-black)' : '#FFFFFF',
                      color: isSelected ? '#FFFFFF' : 'var(--text-secondary)',
                      transition: 'all 0.15s ease',
                      boxShadow: isSelected ? 'var(--shadow-xs)' : 'none'
                    }}
                  >
                    {p.name}
                  </button>
                );
              })}
            </div>

            {/* Live Token Specs Bar */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 14,
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 11.5,
              color: 'var(--text-secondary)',
              background: '#FFFFFF',
              border: '1px solid var(--border-cream)',
              padding: '6px 12px',
              borderRadius: 8
            }}>
              <span><span style={{ color: 'var(--text-muted)' }}>Model:</span> <strong>{preview.model}</strong></span>
              <span><span style={{ color: 'var(--text-muted)' }}>Cost:</span> <strong style={{ color: '#059669' }}>{preview.tokens}</strong></span>
            </div>
          </div>

          {/* Dual-Workbench Container */}
          <div style={{
            background: 'var(--term-bg)',
            border: '1px solid var(--term-border)',
            borderRadius: 18,
            boxShadow: 'var(--shadow-term)',
            overflow: 'hidden',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(min(280px, 100%), 1fr))'
          }}>
            
            {/* Left Column: Live Terminal Stream */}
            <div style={{
              borderRight: '1px solid var(--term-border)',
              display: 'flex',
              flexDirection: 'column',
              fontFamily: "'JetBrains Mono', monospace"
            }}>
              {/* Terminal Titlebar */}
              <div style={{
                background: 'var(--term-header)',
                padding: '12px 18px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                borderBottom: '1px solid var(--term-border)'
              }}>
                <div style={{ display: 'flex', gap: 7 }}>
                  <span style={{ width: 11, height: 11, borderRadius: '50%', background: '#EF4444' }}></span>
                  <span style={{ width: 11, height: 11, borderRadius: '50%', background: '#F59E0B' }}></span>
                  <span style={{ width: 11, height: 11, borderRadius: '50%', background: '#10B981' }}></span>
                </div>
                <span style={{ fontSize: 12, color: '#94a3b8', fontWeight: 600 }}>
                  utim-terminal-agent
                </span>
                <span style={{ fontSize: 11, color: '#4ade80', background: 'rgba(74, 222, 128, 0.1)', padding: '2px 6px', borderRadius: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#4ade80' }}></span>
                  ACTIVE
                </span>
              </div>

              {/* Terminal Content */}
              <div style={{ padding: '20px 22px', flex: 1, color: 'var(--term-text)', fontSize: 13, lineHeight: 1.8 }}>
                {/* Prompt box */}
                <div style={{
                  background: 'rgba(255, 255, 255, 0.04)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: 8,
                  padding: '10px 14px',
                  marginBottom: 16,
                  color: '#FFFFFF'
                }}>
                  <div style={{ fontSize: 11, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4 }}>
                    Developer Prompt
                  </div>
                  <div style={{ fontWeight: 600 }}>
                    "{preview.prompt}"
                  </div>
                </div>

                {/* Steps output with Fast Stagger */}
                <AnimatePresence mode="wait">
                  <motion.div
                    key={preview.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.2 }}
                    style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
                  >
                    {preview.terminalSteps.map((s, idx) => {
                      let color = '#cbd5e1';
                      if (s.type === 'step') color = '#38bdf8';
                      if (s.type === 'tool') color = '#facc15';
                      if (s.type === 'success') color = '#4ade80';
                      if (s.type === 'done') color = '#FFFFFF';

                      return (
                        <motion.div 
                          key={idx}
                          initial={{ opacity: 0, x: -6 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ duration: 0.15, delay: idx * 0.04 }}
                          style={{ color, fontSize: 12.5 }}
                        >
                          {s.text}
                        </motion.div>
                      );
                    })}
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>

            {/* Right Column: Code Diff Inspector */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              background: '#0a0a0d',
              fontFamily: "'JetBrains Mono', monospace"
            }}>
              {/* Diff Titlebar */}
              <div style={{
                background: 'var(--term-header)',
                padding: '12px 18px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                borderBottom: '1px solid var(--term-border)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#f8fafc', fontSize: 12.5, fontWeight: 600 }}>
                  <FileCode size={15} color="#38bdf8" />
                  <span>{preview.file}</span>
                </div>
                <span style={{ fontSize: 11, color: '#38bdf8', background: 'rgba(56, 189, 248, 0.1)', padding: '2px 8px', borderRadius: 4 }}>
                  ATOMIC DIFF
                </span>
              </div>

              {/* Code Diff Lines */}
              <div style={{ padding: '18px 20px', flex: 1, overflowX: 'auto', fontSize: 12.5, lineHeight: 1.7 }}>
                <AnimatePresence mode="wait">
                  <motion.div
                    key={preview.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    {preview.diff.map((line, lIdx) => {
                      let bg = 'transparent';
                      let color = '#94a3b8';

                      if (line.type === 'add') {
                        bg = 'rgba(74, 222, 128, 0.08)';
                        color = '#86efac';
                      } else if (line.type === 'del') {
                        bg = 'rgba(239, 68, 68, 0.12)';
                        color = '#fca5a5';
                      } else if (line.type === 'header') {
                        color = '#64748b';
                      } else if (line.type === 'normal') {
                        color = '#cbd5e1';
                      }

                      return (
                        <motion.div
                          key={lIdx}
                          initial={{ opacity: 0, x: 4 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ duration: 0.12, delay: lIdx * 0.02 }}
                          style={{
                            background: bg,
                            color,
                            padding: '2px 6px',
                            borderRadius: 3,
                            whiteSpace: 'pre',
                            marginBottom: 2
                          }}
                        >
                          {line.text}
                        </motion.div>
                      );
                    })}
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>

          </div>
        </motion.div>

      </div>
    </section>
  );
}
