import React, { useState } from 'react';
import { Terminal, Play, Copy, Check, Sparkles, RefreshCw, Layers, Shield, Cpu, RotateCcw, Share2, Mic, DollarSign } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const COMMANDS = [
  {
    id: 'plan',
    name: '/plan',
    label: 'Autonomous Planning',
    icon: Sparkles,
    input: 'utim /plan "Build a secure webhook handler for Stripe with idempotency keys"',
    output: [
      { type: 'system', text: '⚡ UTIM Planning Engine v2.1.3 activated.' },
      { type: 'info', text: '🧠 Querying local ChromaDB vector memory for repository architecture...' },
      { type: 'step', text: '1/4 [PLAN] Discovered existing Express server in `src/server.ts`.' },
      { type: 'step', text: '2/4 [CREATE] Writing idempotency middleware in `src/middleware/idempotency.ts`.' },
      { type: 'step', text: '3/4 [EDIT] Mounting `/api/webhooks/stripe` endpoint with raw body signature verification.' },
      { type: 'step', text: '4/4 [TEST] Running `npm test -- --grep "webhook"` to verify signature replay protection.' },
      { type: 'success', text: '✓ All 4 tasks completed autonomously. Zero human intervention needed.' },
    ],
  },
  {
    id: 'model',
    name: '/model',
    label: 'Model Switching',
    icon: Cpu,
    input: 'utim /model anthropic/claude-sonnet-4.6',
    output: [
      { type: 'system', text: '⚡ Model registry reconfigured.' },
      { type: 'info', text: 'Active Provider: Anthropic (Tier: Professional Core)' },
      { type: 'info', text: 'Context Window: 1,000,000 tokens | Max Output: 128,000 tokens' },
      { type: 'success', text: '✓ Switched reasoning engine to Claude Sonnet 4.6.' },
      { type: 'dim', text: 'Quota balance remaining: 18,000 monthly credits + 2,000 bonus credits.' },
    ],
  },
  {
    id: 'undo',
    name: '/undo',
    label: 'Rollback & Rewind',
    icon: RotateCcw,
    input: 'utim /undo 2',
    output: [
      { type: 'system', text: '⚡ Reversible Execution Engine' },
      { type: 'info', text: 'Inspecting last 2 atomic filesystem transactions...' },
      { type: 'step', text: '⏪ Reverted `src/components/Checkout.tsx` (restored 42 lines)' },
      { type: 'step', text: '⏪ Removed scratch artifact `tests/e2e/temp_test.js`' },
      { type: 'success', text: '✓ Repository cleanly restored to state at 23:14:02. Zero Git conflicts.' },
    ],
  },
  {
    id: 'voice',
    name: '/voice',
    label: 'Voice Dictation',
    icon: Mic,
    input: 'utim /voice --mic "Refactor the database connection pool to use 20 max clients"',
    output: [
      { type: 'system', text: '🎙️ Streaming audio transcription via Whisper...' },
      { type: 'info', text: 'Heard: "Refactor the database connection pool to use 20 max clients"' },
      { type: 'step', text: '🔍 Found `src/db/pool.ts`. Updating `max: 20` and connection timeout to `5000ms`.' },
      { type: 'success', text: '✓ Database pool refactored and TypeScript check passed cleanly.' },
    ],
  },
  {
    id: 'cost',
    name: '/cost',
    label: 'Token & Cost Tracker',
    icon: DollarSign,
    input: 'utim /cost --detailed',
    output: [
      { type: 'system', text: '📊 Session Token Consumption Report' },
      { type: 'info', text: 'Session Duration: 18m 42s | Tool Invocations: 14' },
      { type: 'step', text: 'Input Tokens: 34,210 ($0.034) | Output Tokens: 2,140 ($0.032)' },
      { type: 'step', text: 'ChromaDB Embeddings: 12,400 tokens ($0.000 Free Local)' },
      { type: 'success', text: 'Total Session Compute: 66 credits consumed. Remaining balance: 17,934 credits.' },
    ],
  },
  {
    id: 'share',
    name: '/share',
    label: 'Workspace Export',
    icon: Share2,
    input: 'utim /share --include-diff --zip',
    output: [
      { type: 'system', text: '📦 Bundling interactive session trajectory...' },
      { type: 'info', text: 'Compressing 8 file changes, execution transcripts, and test logs...' },
      { type: 'success', text: '✓ Secure share link generated: https://utim.dev/share/wks_7a9f2b' },
      { type: 'dim', text: 'Link is encrypted and available for 30 days.' },
    ],
  },
];

export default function InteractiveCliPlayground() {
  const [activeCmdId, setActiveCmdId] = useState('plan');
  const [copied, setCopied] = useState(false);

  const activeCmd = COMMANDS.find((c) => c.id === activeCmdId) || COMMANDS[0];

  const handleCopy = () => {
    navigator.clipboard.writeText(activeCmd.input);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section className="st-playground-section" style={{ padding: '80px 24px', background: 'var(--bg-cream-alt)', borderTop: '1px solid var(--border-cream)', borderBottom: '1px solid var(--border-cream)' }}>
      <div className="st-container">
        
        {/* Section Header */}
        <div className="st-section-header">
          <div className="st-hero-badge">
            <Terminal size={14} /> INTERACTIVE COMMAND PLAYGROUND
          </div>
          <h2 className="st-section-title">
            Test UTIM CLI Commands Live
          </h2>
          <p className="st-section-subtitle">
            Click any command shortcut to preview how UTIM reasons, inspects local files, executes tools, and tracks compute costs.
          </p>
        </div>

        {/* Command Selector Chips */}
        <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 28 }}>
          {COMMANDS.map((cmd) => {
            const Icon = cmd.icon;
            const isSelected = cmd.id === activeCmdId;
            return (
              <button
                key={cmd.id}
                onClick={() => setActiveCmdId(cmd.id)}
                className={`st-term-prompt-chip ${isSelected ? 'active' : ''}`}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '10px 18px',
                  borderRadius: 10,
                  fontSize: 13.5,
                  fontWeight: 700,
                  cursor: 'pointer',
                  border: isSelected ? '1px solid var(--accent-black)' : '1px solid var(--border-cream)',
                  background: isSelected ? 'var(--accent-black)' : '#FFFFFF',
                  color: isSelected ? '#FFFFFF' : 'var(--text-primary)',
                  boxShadow: isSelected ? 'var(--shadow-sm)' : 'none',
                  transition: 'all 0.15s ease'
                }}
              >
                <Icon size={15} />
                <span>{cmd.name}</span>
                <span style={{ fontSize: 11, opacity: isSelected ? 0.8 : 0.6, fontWeight: 500 }}>
                  ({cmd.label})
                </span>
              </button>
            );
          })}
        </div>

        {/* Live Terminal Preview Box */}
        <div style={{ maxWidth: 840, margin: '0 auto' }}>
          <div style={{
            background: 'var(--term-bg)',
            border: '1px solid var(--term-border)',
            borderRadius: 16,
            boxShadow: 'var(--shadow-term)',
            overflow: 'hidden',
            fontFamily: "'JetBrains Mono', monospace"
          }}>
            {/* Window Topbar */}
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
              <span style={{ color: '#94a3b8', fontSize: 12, fontWeight: 600 }}>
                utim-terminal-session (~/workspace)
              </span>
              <button
                onClick={handleCopy}
                style={{
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  color: '#e2e8f0',
                  borderRadius: 6,
                  padding: '4px 10px',
                  fontSize: 12,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  cursor: 'pointer'
                }}
              >
                {copied ? <><Check size={12} color="#10B981" /> Copied</> : <><Copy size={12} /> Copy</>}
              </button>
            </div>

            {/* Terminal Body */}
            <div style={{ padding: '18px 20px', minHeight: 280, color: 'var(--term-text)', fontSize: 13.5, lineHeight: 1.8, overflowWrap: 'anywhere', wordBreak: 'break-word' }}>
              {/* Input Command Line */}
              <div style={{ display: 'flex', gap: 10, marginBottom: 18, color: '#f8fafc', fontWeight: 600, overflowWrap: 'anywhere' }}>
                <span style={{ color: 'var(--term-cyan)', flexShrink: 0 }}>$</span>
                <span>{activeCmd.input}</span>
              </div>

              {/* Output Lines with Smooth Fade Animation */}
              <AnimatePresence mode="wait">
                <motion.div
                  key={activeCmd.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.18 }}
                  style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
                >
                  {activeCmd.output.map((line, idx) => {
                    let color = '#cbd5e1';
                    if (line.type === 'system') color = 'var(--term-yellow)';
                    if (line.type === 'info') color = 'var(--term-cyan)';
                    if (line.type === 'step') color = '#f1f5f9';
                    if (line.type === 'success') color = 'var(--term-green)';
                    if (line.type === 'dim') color = '#64748b';

                    return (
                      <div key={idx} style={{ color, overflowWrap: 'anywhere' }}>
                        {line.text}
                      </div>
                    );
                  })}
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        </div>

      </div>
    </section>
  );
}
