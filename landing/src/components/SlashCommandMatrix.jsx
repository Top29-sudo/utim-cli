import React, { useState, useEffect } from 'react';
import { 
  Terminal, RotateCcw, Cpu, Mic, DollarSign, 
  Share2, Wrench, Layers, CornerDownLeft, Sparkles 
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const COMMANDS = [
  {
    key: 'P',
    cmd: '/plan',
    name: 'Checklist Task Graph',
    icon: Cpu,
    desc: 'Break any complex feature or refactor into structured, parallel tasks with automatic subagent delegation.',
    output: `[PLANNER] Feature Decomposition:
1. [✓] Parse AST export signatures in src/index.ts
2. [✓] Generate Redis token bucket limiter in src/limiter.ts
3. [✓] Write 100-concurrency load test in tests/load.test.ts
4. [•] Execute unit tests & verify memory leaks`
  },
  {
    key: 'U',
    cmd: '/undo',
    name: 'Instant Reversion',
    icon: RotateCcw,
    desc: 'Instantly revert the last turn, file edit, or multi-directory refactor with 0 git conflicts.',
    output: `[UNDO] Inspecting session turn #8...
→ Reverted src/limiter.ts (-48 lines)
→ Removed uncommitted test artifact test_report.json
✓ Workspace rolled back to clean baseline.`
  },
  {
    key: 'M',
    cmd: '/model',
    name: 'Multi-Model Switcher',
    icon: Terminal,
    desc: 'Hot-swap between Claude 3.7 Sonnet, DeepSeek R1, GPT-5.4, or free local/hosted models in mid-session.',
    output: `[MODEL REGISTRY] Active model: anthropic/claude-sonnet-4.6
→ Switched to: deepseek/deepseek-r1 (Reasoning Mode: ACTIVE)
→ Subagent 1 model: google/gemini-3.6-flash (Fast Lookup)
✓ Model configuration updated without resetting chat context.`
  },
  {
    key: 'V',
    cmd: '/voice',
    name: 'Real-time Voice Coding',
    icon: Mic,
    desc: 'Speak naturally to UTIM to dictate instructions, explain edge cases, or review code hands-free.',
    output: `[VOICE AUDIO STREAM] Listening via default microphone...
→ Transcribed: "Refactor the database connection pool to handle idle timeouts"
[AGENT] Executing prompt... Updating src/db/pool.ts`
  },
  {
    key: 'C',
    cmd: '/cost',
    name: 'Token Compute HUD',
    icon: DollarSign,
    desc: 'Audit real-time prompt tokens, completion tokens, latency, and credit usage with complete transparency.',
    output: `[SESSION COMPUTE AUDIT]
Prompt Tokens: 4,120 ($0.012)
Completion Tokens: 890 ($0.008)
ChromaDB Vector Retrieval: 12ms (Local, $0.000)
Total Session Cost: $0.020 | Balance: 17,940 credits remaining`
  },
  {
    key: 'S',
    cmd: '/share',
    name: 'Instant Team Context Link',
    icon: Share2,
    desc: 'Export the complete workspace state, session transcript, and diff history to a secure team URL.',
    output: `[WORKSPACE EXPORT] Packaging session context...
✓ Encrypted snapshot created (AES-256)
→ Shareable Link: https://utim.dev/s/8f92a-live-refactor
Teammates can run: utim --join 8f92a to resume.`
  }
];

export default function SlashCommandMatrix() {
  const [selectedCmd, setSelectedCmd] = useState(COMMANDS[0]);

  // Keyboard shortcut listener
  useEffect(() => {
    const onKeyDown = (e) => {
      // Don't trigger if user is typing in an input
      if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return;
      const match = COMMANDS.find(c => c.key.toLowerCase() === e.key.toLowerCase());
      if (match) {
        setSelectedCmd(match);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  return (
    <section style={{ padding: '80px 24px', background: 'var(--bg-cream-alt)', borderTop: '1px solid var(--border-cream)' }}>
      <div className="st-container">
        
        {/* Section Header with Scroll Trigger */}
        <motion.div 
          initial={{ opacity: 0, y: 22 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.38, ease: [0.16, 1, 0.3, 1] }}
          className="st-section-header" 
          style={{ marginBottom: 36 }}
        >
          <div className="st-hero-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '0', background: 'transparent', border: 'none', borderRadius: 0, fontSize: 12.5, fontWeight: 600 }}>
            <Terminal size={13} color="var(--accent-brand)" />
            <span>Keyboard-first developer HUD</span>
          </div>
          <h2 className="st-section-title">
            Slash Commands Built for Speed
          </h2>
          <p className="st-section-subtitle">
            Control the entire agent loop directly from your keyboard without touching the mouse.
          </p>
        </motion.div>

        {/* Command Matrix Grid & Live Terminal Preview with Stagger Animation */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: 24,
          alignItems: 'start'
        }}>
          
          {/* Left: Interactive Command Keys */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
            {COMMANDS.map((c, idx) => {
              const isSelected = c.cmd === selectedCmd.cmd;
              const Icon = c.icon;
              return (
                <motion.button
                  key={c.cmd}
                  initial={{ opacity: 0, y: 16 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: '-60px' }}
                  transition={{ duration: 0.3, delay: idx * 0.05, ease: [0.16, 1, 0.3, 1] }}
                  onClick={() => setSelectedCmd(c)}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'flex-start',
                    padding: '16px 18px',
                    borderRadius: 12,
                    border: isSelected ? '1.5px solid var(--accent-black)' : '1px solid var(--border-cream)',
                    background: isSelected ? 'var(--accent-black)' : '#FFFFFF',
                    color: isSelected ? '#FFFFFF' : 'var(--text-primary)',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    boxShadow: isSelected ? 'var(--shadow-sm)' : 'var(--shadow-xs)',
                    textAlign: 'left'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', marginBottom: 10 }}>
                    <span style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 14,
                      fontWeight: 800,
                      color: isSelected ? '#38bdf8' : 'var(--text-primary)'
                    }}>
                      {c.cmd}
                    </span>
                    <kbd style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 11,
                      fontWeight: 700,
                      background: isSelected ? 'rgba(255, 255, 255, 0.18)' : 'var(--bg-cream)',
                      color: isSelected ? '#FFFFFF' : 'var(--text-secondary)',
                      padding: '2px 7px',
                      borderRadius: 4,
                      border: isSelected ? '1px solid rgba(255,255,255,0.2)' : '1px solid var(--border-cream)'
                    }}>
                      {c.key}
                    </kbd>
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 750, marginBottom: 4 }}>
                    {c.name}
                  </div>
                  <div style={{ fontSize: 12, color: isSelected ? '#cbd5e1' : 'var(--text-secondary)', lineHeight: 1.4 }}>
                    {c.desc}
                  </div>
                </motion.button>
              );
            })}
          </div>

          {/* Right: Live Interactive Terminal Window with Entrance Slide */}
          <motion.div 
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            whileInView={{ opacity: 1, y: 0, scale: 1 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ duration: 0.4, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
            style={{
              background: 'var(--term-bg)',
              border: '1px solid var(--term-border)',
              borderRadius: 16,
              overflow: 'hidden',
              boxShadow: 'var(--shadow-term)',
              fontFamily: "'JetBrains Mono', monospace"
            }}
          >
            <div style={{
              background: 'var(--term-header)',
              padding: '12px 18px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderBottom: '1px solid var(--term-border)'
            }}>
              <div style={{ display: 'flex', gap: 6 }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#EF4444' }}></span>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#F59E0B' }}></span>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#10B981' }}></span>
              </div>
              <span style={{ fontSize: 12, color: '#94a3b8', fontWeight: 600 }}>
                {selectedCmd.cmd} output
              </span>
              <span style={{ fontSize: 11, color: '#38bdf8', background: 'rgba(56, 189, 248, 0.1)', padding: '2px 6px', borderRadius: 4 }}>
                PRESS [{selectedCmd.key}]
              </span>
            </div>

            <div style={{ padding: '24px', fontSize: 13, lineHeight: 1.75, minHeight: 220 }}>
              <div style={{ color: '#38bdf8', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: '#4ade80' }}>❯</span>
                <span style={{ fontWeight: 700 }}>utim {selectedCmd.cmd}</span>
              </div>

              <AnimatePresence mode="wait">
                <motion.pre
                  key={selectedCmd.cmd}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.15 }}
                  style={{ margin: 0, color: '#e2e8f0', whiteSpace: 'pre-wrap', fontFamily: "'JetBrains Mono', monospace", fontSize: 12.5 }}
                >
                  <code>{selectedCmd.output}</code>
                </motion.pre>
              </AnimatePresence>
            </div>
          </motion.div>

        </div>

      </div>
    </section>
  );
}
