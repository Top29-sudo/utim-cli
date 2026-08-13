import React, { useState } from 'react';
import { 
  RotateCcw, History, GitCommit, Play, 
  CheckCircle2, AlertTriangle, ArrowRight, 
  FileCode, Terminal, Sparkles, Clock, RefreshCw 
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const CHECKPOINTS = [
  {
    step: 1,
    time: '10:14:02 AM',
    label: 'Initial State',
    action: 'Developer prompts: "Add OAuth2 PKCE login flow with GitHub & Google"',
    status: 'clean',
    badge: 'BASELINE',
    files: [
      { name: 'src/server.ts', status: 'clean' },
      { name: 'src/routes/auth.ts', status: 'missing' },
      { name: 'src/lib/oauth.ts', status: 'missing' },
      { name: 'tests/auth.test.ts', status: 'missing' }
    ],
    terminalLog: [
      '$ utim "Add OAuth2 PKCE login flow with GitHub & Google"',
      '[PLAN] Created execution graph with 3 atomic tasks.',
      '[AST] Inspected `src/server.ts` export bindings.'
    ],
    codeSnippet: {
      file: 'src/server.ts',
      diff: [
        { type: 'normal', text: 'import express from "express";' },
        { type: 'normal', text: 'const app = express();' },
        { type: 'normal', text: 'app.listen(3000);' }
      ]
    }
  },
  {
    step: 2,
    time: '10:15:18 AM',
    label: 'Agent Code Generation',
    action: 'Agent generated PKCE verifier generation & route handlers',
    status: 'modified',
    badge: 'FILES WRITTEN',
    files: [
      { name: 'src/server.ts', status: 'modified' },
      { name: 'src/routes/auth.ts', status: 'added' },
      { name: 'src/lib/oauth.ts', status: 'added' },
      { name: 'tests/auth.test.ts', status: 'added' }
    ],
    terminalLog: [
      '→ tool_call: write_to_file `src/lib/oauth.ts` (+58 lines)',
      '→ tool_call: write_to_file `src/routes/auth.ts` (+92 lines)',
      '→ tool_call: replace_file_content `src/server.ts` (mounted /auth router)',
      '[TEST] Spawning test runner `npm test`...'
    ],
    codeSnippet: {
      file: 'src/lib/oauth.ts',
      diff: [
        { type: 'add', text: '+ import crypto from "crypto";' },
        { type: 'add', text: '+ export function generatePKCE() {' },
        { type: 'add', text: '+   const verifier = crypto.randomBytes(32).toString("base64url");' },
        { type: 'add', text: '+   const challenge = crypto.createHash("sha256").update(verifier).digest("base64url");' },
        { type: 'add', text: '+   return { verifier, challenge };' },
        { type: 'add', text: '+ }' }
      ]
    }
  },
  {
    step: 3,
    time: '10:16:04 AM',
    label: 'Self-Healing Test Remediated',
    action: 'Test caught missing state token validation → Agent auto-fixed code',
    status: 'healed',
    badge: 'SELF-HEALED',
    files: [
      { name: 'src/server.ts', status: 'modified' },
      { name: 'src/routes/auth.ts', status: 'modified' },
      { name: 'src/lib/oauth.ts', status: 'healed' },
      { name: 'tests/auth.test.ts', status: 'clean' }
    ],
    terminalLog: [
      '⚠ Test Failure: State token mismatch not handled in callback.',
      '⚡ [SELF-HEAL] Re-analyzing error stack trace...',
      '→ tool_call: replace_file_content `src/routes/auth.ts` (added CSRF state check)',
      '✓ All 14 tests passing with 100% branch coverage.'
    ],
    codeSnippet: {
      file: 'src/routes/auth.ts',
      diff: [
        { type: 'normal', text: '  if (!req.query.code) throw new Error("Missing code");' },
        { type: 'add', text: '+ if (req.query.state !== session.csrfToken) {' },
        { type: 'add', text: '+   return res.status(403).json({ error: "Invalid CSRF state" });' },
        { type: 'add', text: '+ }' },
        { type: 'normal', text: '  const tokens = await exchangeCode(req.query.code);' }
      ]
    }
  },
  {
    step: 4,
    time: '10:17:30 AM',
    label: 'Time-Travel /undo Rollback',
    action: 'Developer triggered `/undo` → Instantaneous atomic state reversion',
    status: 'reverted',
    badge: 'REVERSIBLE SNAPSHOT',
    files: [
      { name: 'src/server.ts', status: 'clean' },
      { name: 'src/routes/auth.ts', status: 'missing' },
      { name: 'src/lib/oauth.ts', status: 'missing' },
      { name: 'tests/auth.test.ts', status: 'missing' }
    ],
    terminalLog: [
      '$ utim /undo',
      '[SNAPSHOT] Reverting atomic checkpoint #3 back to #1 baseline...',
      '✓ Restored `src/server.ts` to original state.',
      '✓ Cleaned uncommitted artifacts. Working tree is clean (0 git conflicts).'
    ],
    codeSnippet: {
      file: 'src/server.ts',
      diff: [
        { type: 'header', text: '@@ Reverted cleanly to checkpoint #1 @@' },
        { type: 'del', text: '- import { authRouter } from "./routes/auth";' },
        { type: 'del', text: '- app.use("/auth", authRouter);' },
        { type: 'normal', text: '  app.listen(3000);' }
      ]
    }
  }
];

export default function TimeTravelRewindVisualizer() {
  const [activeStepIndex, setActiveStepIndex] = useState(2); // default to step 3 (Self-Healed)
  const current = CHECKPOINTS[activeStepIndex];

  return (
    <section style={{ padding: '90px 24px', background: '#FFFFFF', borderTop: '1px solid var(--border-cream)', borderBottom: '1px solid var(--border-cream)', position: 'relative' }}>
      <div className="st-container">
        
        {/* Section Header with Scroll Trigger */}
        <motion.div 
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.38, ease: [0.16, 1, 0.3, 1] }}
          className="st-section-header" 
          style={{ marginBottom: 40 }}
        >
          <div className="st-hero-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '0', background: 'transparent', borderRadius: 0, fontSize: 12.5, fontWeight: 600 }}>
            <RotateCcw size={13} color="var(--accent-brand)" />
            <span>Atomic time-travel engine</span>
          </div>
          <h2 className="st-section-title">
            Reversible Snapshots &amp; Zero Git Conflicts
          </h2>
          <p className="st-section-subtitle">
            Every prompt, file edit, and test failure creates an atomic timeline checkpoint. Scrub through time or run <code>/undo</code> without touching git stash.
          </p>
        </motion.div>

        {/* Interactive Timeline Scrubber Bar with Scroll Trigger */}
        <motion.div 
          initial={{ opacity: 0, y: 28, scale: 0.98 }}
          whileInView={{ opacity: 1, y: 0, scale: 1 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.42, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
          style={{
            background: 'var(--bg-cream)',
            border: '1px solid var(--border-cream)',
            borderRadius: 16,
            padding: '24px 28px',
            marginBottom: 32,
            boxShadow: 'var(--shadow-xs)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Clock size={16} color="var(--text-secondary)" />
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                Interactive session timeline scrubber
              </span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600 }}>
              Click any checkpoint or drag slider to travel through time
            </div>
          </div>

          {/* Stepper Buttons */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
            {CHECKPOINTS.map((cp, idx) => {
              const isSelected = idx === activeStepIndex;
              return (
                <button
                  key={cp.step}
                  onClick={() => setActiveStepIndex(idx)}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'flex-start',
                    padding: '12px 16px',
                    borderRadius: 10,
                    border: isSelected ? '1.5px solid var(--accent-black)' : '1px solid var(--border-cream)',
                    background: isSelected ? 'var(--accent-black)' : '#FFFFFF',
                    color: isSelected ? '#FFFFFF' : 'var(--text-primary)',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    boxShadow: isSelected ? 'var(--shadow-sm)' : 'none',
                    textAlign: 'left'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', marginBottom: 4 }}>
                    <span style={{ fontSize: 11, fontWeight: 800, color: isSelected ? '#38bdf8' : 'var(--text-muted)' }}>
                      STEP 0{cp.step}
                    </span>
                    <span style={{ fontSize: 10.5, fontWeight: 700, padding: '2px 6px', borderRadius: 4, background: isSelected ? 'rgba(255, 255, 255, 0.15)' : 'var(--bg-cream)', color: isSelected ? '#FFFFFF' : 'var(--text-secondary)' }}>
                      {cp.time}
                    </span>
                  </div>
                  <div style={{ fontSize: 13.5, fontWeight: 800, lineHeight: 1.25 }}>
                    {cp.label}
                  </div>
                </button>
              );
            })}
          </div>
        </motion.div>

        {/* Live Visualizer Stage (File Tree + Terminal Log + Code Diff) */}
        <motion.div 
          initial={{ opacity: 0, y: 32 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.45, delay: 0.14, ease: [0.16, 1, 0.3, 1] }}
          style={{
            background: 'var(--term-bg)',
            borderRadius: 16,
            border: '1px solid var(--term-border)',
            overflow: 'hidden',
            boxShadow: 'var(--shadow-term)',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            minHeight: 360
          }}
        >
          
          {/* Column 1: Live File Tree State */}
          <div style={{
            borderRight: '1px solid var(--term-border)',
            padding: '18px',
            background: '#090a0c',
            fontFamily: "'JetBrains Mono', monospace"
          }}>
            <div style={{ fontSize: 11, fontWeight: 800, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
              <GitCommit size={14} color="#38bdf8" />
              <span>Workspace Files</span>
            </div>

            <AnimatePresence mode="wait">
              <motion.div
                key={current.step}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 6 }}
                transition={{ duration: 0.15 }}
                style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
              >
                {current.files.map((f, fIdx) => {
                  let color = '#94a3b8';
                  let statusTag = '';
                  let tagBg = 'transparent';

                  if (f.status === 'clean') {
                    color = '#cbd5e1';
                    statusTag = 'ORIGINAL';
                    tagBg = 'rgba(255,255,255,0.06)';
                  } else if (f.status === 'added') {
                    color = '#4ade80';
                    statusTag = '+NEW';
                    tagBg = 'rgba(74, 222, 128, 0.15)';
                  } else if (f.status === 'modified') {
                    color = '#facc15';
                    statusTag = 'MODIFIED';
                    tagBg = 'rgba(250, 204, 21, 0.15)';
                  } else if (f.status === 'healed') {
                    color = '#38bdf8';
                    statusTag = 'HEALED';
                    tagBg = 'rgba(56, 189, 248, 0.15)';
                  } else if (f.status === 'missing') {
                    color = '#475569';
                    statusTag = 'UNTOUCHED';
                    tagBg = 'rgba(255,255,255,0.03)';
                  }

                  return (
                    <div
                      key={fIdx}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '6px 8px',
                        borderRadius: 6,
                        background: 'rgba(255, 255, 255, 0.02)',
                        fontSize: 12
                      }}
                    >
                      <span style={{ color, textDecoration: f.status === 'missing' ? 'line-through' : 'none' }}>
                        {f.name}
                      </span>
                      <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 5px', borderRadius: 4, background: tagBg, color }}>
                        {statusTag}
                      </span>
                    </div>
                  );
                })}
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Column 2: Terminal Step Execution Stream */}
          <div style={{
            borderRight: '1px solid var(--term-border)',
            padding: '18px 20px',
            fontFamily: "'JetBrains Mono', monospace",
            display: 'flex',
            flexDirection: 'column'
          }}>
            <div style={{ fontSize: 11, fontWeight: 800, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Terminal size={14} color="#facc15" />
              <span>Execution Transcript</span>
            </div>

            <div style={{
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 8,
              padding: '8px 12px',
              fontSize: 12,
              color: '#FFFFFF',
              fontWeight: 600,
              marginBottom: 14
            }}>
              {current.action}
            </div>

            <AnimatePresence mode="wait">
              <motion.div
                key={current.step}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12, color: '#cbd5e1', lineHeight: 1.6 }}
              >
                {current.terminalLog.map((log, lIdx) => (
                  <div key={lIdx} style={{ color: log.startsWith('✓') ? '#4ade80' : log.startsWith('⚠') ? '#f87171' : log.startsWith('$') ? '#38bdf8' : '#e2e8f0' }}>
                    {log}
                  </div>
                ))}
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Column 3: Live Syntax Diff Hunk */}
          <div style={{
            padding: '18px 20px',
            fontFamily: "'JetBrains Mono', monospace",
            background: '#07080a',
            overflowX: 'auto'
          }}>
            <div style={{ fontSize: 11, fontWeight: 800, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 14, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <FileCode size={14} color="#4ade80" />
                <span>{current.codeSnippet.file}</span>
              </div>
              <span style={{ fontSize: 10, color: '#4ade80', background: 'rgba(74, 222, 128, 0.1)', padding: '2px 6px', borderRadius: 4 }}>
                {current.badge}
              </span>
            </div>

            <AnimatePresence mode="wait">
              <motion.div
                key={current.step}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                style={{ fontSize: 12, lineHeight: 1.7 }}
              >
                {current.codeSnippet.diff.map((d, dIdx) => {
                  let bg = 'transparent';
                  let color = '#94a3b8';

                  if (d.type === 'add') {
                    bg = 'rgba(74, 222, 128, 0.1)';
                    color = '#86efac';
                  } else if (d.type === 'del') {
                    bg = 'rgba(239, 68, 68, 0.15)';
                    color = '#fca5a5';
                  } else if (d.type === 'header') {
                    color = '#38bdf8';
                  } else if (d.type === 'normal') {
                    color = '#cbd5e1';
                  }

                  return (
                    <div key={dIdx} style={{ background: bg, color, padding: '2px 6px', borderRadius: 3, whiteSpace: 'pre', marginBottom: 2 }}>
                      {d.text}
                    </div>
                  );
                })}
              </motion.div>
            </AnimatePresence>
          </div>

        </motion.div>

      </div>
    </section>
  );
}
