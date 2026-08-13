import React, { useState, useEffect } from 'react';
import { 
  Cpu, Search, Wrench, CheckCircle2, 
  Sparkles, Layers, ArrowRight, Play, 
  RotateCcw, ShieldCheck, Zap, Activity 
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const SWARM_STEPS = [
  {
    id: 1,
    name: '1. Task Decomposition',
    activeNode: 'root',
    orchestratorMsg: 'Parsing prompt: "Build multi-tenant JWT middleware with Redis token revocation"',
    workers: [
      { id: 'researcher', role: 'ChromaDB AST Ingester', status: 'idle', task: 'Waiting for symbol query' },
      { id: 'coder', role: 'Multi-File Patch Engine', status: 'idle', task: 'Waiting for context bundle' },
      { id: 'tester', role: 'Self-Healing Test Runner', status: 'idle', task: 'Waiting for generated test spec' }
    ],
    packetFlow: 'root -> all'
  },
  {
    id: 2,
    name: '2. Parallel Subagent Dispatch',
    activeNode: 'researcher',
    orchestratorMsg: 'Dispatched 3 parallel subagent workers concurrently via async event loop.',
    workers: [
      { id: 'researcher', role: 'ChromaDB AST Ingester', status: 'active', task: 'Queried vector graph: found `auth/jwt.ts` and `tenant/schema.ts` (0.94 cosine)' },
      { id: 'coder', role: 'Multi-File Patch Engine', status: 'active', task: 'Scaffolding `middleware/auth.ts` with Redis token blocklist' },
      { id: 'tester', role: 'Self-Healing Test Runner', status: 'standby', task: 'Compiling 18 test cases in `tests/auth.test.ts`' }
    ],
    packetFlow: 'researcher -> coder'
  },
  {
    id: 3,
    name: '3. Multi-File Atomic Patching',
    activeNode: 'coder',
    orchestratorMsg: 'Applying atomic AST diffs across `src/middleware/auth.ts` & `src/server.ts`.',
    workers: [
      { id: 'researcher', role: 'ChromaDB AST Ingester', status: 'done', task: 'Index complete (14 symbols retrieved in 8ms)' },
      { id: 'coder', role: 'Multi-File Patch Engine', status: 'active', task: 'Wrote 74 lines of TypeScript with zero lint errors' },
      { id: 'tester', role: 'Self-Healing Test Runner', status: 'active', task: 'Executing `npm test` against local Docker Redis instance...' }
    ],
    packetFlow: 'coder -> tester'
  },
  {
    id: 4,
    name: '4. Self-Healing Test Remediation',
    activeNode: 'tester',
    orchestratorMsg: 'Test caught missing Redis disconnect teardown. Tester subagent auto-healed code in 120ms.',
    workers: [
      { id: 'researcher', role: 'ChromaDB AST Ingester', status: 'done', task: 'Memory cached in `.utim/chroma`' },
      { id: 'coder', role: 'Multi-File Patch Engine', status: 'done', task: 'Added `redis.quit()` inside `afterAll()` hook' },
      { id: 'tester', role: 'Self-Healing Test Runner', status: 'done', task: '✓ 18/18 Tests Passed (100% Branch Coverage)' }
    ],
    packetFlow: 'tester -> root'
  }
];

export default function SubagentSwarmVisualizer() {
  const [currentStepIdx, setCurrentStepIdx] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);

  const step = SWARM_STEPS[currentStepIdx];

  // Auto-cycle through the swarm stages when playing
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setCurrentStepIdx((prev) => (prev + 1) % SWARM_STEPS.length);
    }, 3600);
    return () => clearInterval(interval);
  }, [isPlaying]);

  return (
    <section style={{ padding: '85px 24px', background: '#FFFFFF', borderTop: '1px solid var(--border-cream)', borderBottom: '1px solid var(--border-cream)', position: 'relative', overflow: 'hidden' }}>
      
      {/* Background Matrix Grid Pattern */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundImage: 'radial-gradient(rgba(18, 18, 20, 0.05) 1px, transparent 1px)',
        backgroundSize: '24px 24px',
        pointerEvents: 'none',
        zIndex: 0
      }} />

      <div className="st-container" style={{ position: 'relative', zIndex: 1 }}>
        
        {/* Section Header */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.38, ease: [0.16, 1, 0.3, 1] }}
          className="st-section-header" 
          style={{ marginBottom: 36 }}
        >
          <div className="st-hero-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '0', background: 'transparent', borderRadius: 0, fontSize: 12.5, fontWeight: 600 }}>
            <Zap size={13} color="var(--accent-brand)" />
            <span>Autonomous swarm orchestration</span>
          </div>
          <h2 className="st-section-title">
            Parallel Subagents Working in Sync
          </h2>
          <p className="st-section-subtitle">
            UTIM doesn't just prompt one model. It breaks your intent into a task graph and dispatches specialized background workers concurrently.
          </p>
        </motion.div>

        {/* Interactive Step Controller Toolbar */}
        <div style={{
          background: 'var(--bg-cream-alt)',
          border: '1px solid var(--border-cream)',
          borderRadius: 14,
          padding: '12px 18px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
          marginBottom: 28
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            {SWARM_STEPS.map((s, idx) => {
              const isCurrent = idx === currentStepIdx;
              return (
                <button
                  key={s.id}
                  onClick={() => {
                    setCurrentStepIdx(idx);
                    setIsPlaying(false);
                  }}
                  style={{
                    padding: '6px 14px',
                    borderRadius: 8,
                    fontSize: 12.5,
                    fontWeight: 750,
                    border: isCurrent ? '1px solid var(--accent-black)' : '1px solid transparent',
                    background: isCurrent ? 'var(--accent-black)' : 'transparent',
                    color: isCurrent ? '#FFFFFF' : 'var(--text-secondary)',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                >
                  {s.name}
                </button>
              );
            })}
          </div>

          <button
            onClick={() => setIsPlaying(!isPlaying)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 12px',
              borderRadius: 8,
              background: '#FFFFFF',
              border: '1px solid var(--border-cream)',
              fontSize: 12,
              fontWeight: 700,
              color: 'var(--text-primary)',
              cursor: 'pointer'
            }}
          >
            {isPlaying ? (
              <><span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10B981' }}></span> Live Auto-Play (3.6s)</>
            ) : (
              <><Play size={12} /> Resume Auto-Play</>
            )}
          </button>
        </div>

        {/* Visual Swarm Canvas Layout */}
        <div className="st-swarm-canvas">
          
          {/* Left Column: Root Orchestrator Hub */}
          <div style={{
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: 14,
            padding: '18px 16px',
            position: 'relative',
            minWidth: 0,
            width: '100%',
            boxSizing: 'border-box'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14, gap: 8, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: 1 }}>
                <div style={{ width: 36, height: 36, borderRadius: 10, background: '#38bdf8', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#090a0f', flexShrink: 0 }}>
                  <Cpu size={20} />
                </div>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: 800, color: '#FFFFFF', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>UTIM Root Orchestrator</div>
                  <div style={{ fontSize: 11, color: '#94a3b8', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>Event Loop Master Node</div>
                </div>
              </div>
              <span style={{ fontSize: 11, color: '#38bdf8', background: 'rgba(56, 189, 248, 0.15)', padding: '3px 8px', borderRadius: 6, fontWeight: 700, flexShrink: 0, marginLeft: 4 }}>
                DISPATCHER
              </span>
            </div>

            <div style={{
              background: '#16161d',
              borderRadius: 10,
              padding: '14px',
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 12,
              color: '#e2e8f0',
              lineHeight: 1.6,
              border: '1px solid rgba(255, 255, 255, 0.06)',
              overflowWrap: 'anywhere',
              wordBreak: 'break-word',
              minWidth: 0
            }}>
              <div style={{ color: '#94a3b8', fontSize: 10.5, marginBottom: 4, textTransform: 'uppercase' }}>
                Active Task State:
              </div>
              <AnimatePresence mode="wait">
                <motion.div
                  key={step.id}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.15 }}
                  style={{ overflowWrap: 'anywhere', wordBreak: 'break-word' }}
                >
                  {step.orchestratorMsg}
                </motion.div>
              </AnimatePresence>
            </div>
          </div>

          {/* Right Column: 3 Parallel Concurrent Subagents */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0, width: '100%' }}>
            {step.workers.map((w, wIdx) => {
              let statusBg = 'rgba(255, 255, 255, 0.05)';
              let statusColor = '#94a3b8';
              let borderColor = 'rgba(255, 255, 255, 0.08)';

              if (w.status === 'active') {
                statusBg = 'rgba(56, 189, 248, 0.12)';
                statusColor = '#38bdf8';
                borderColor = 'rgba(56, 189, 248, 0.4)';
              } else if (w.status === 'done') {
                statusBg = 'rgba(74, 222, 128, 0.12)';
                statusColor = '#4ade80';
                borderColor = 'rgba(74, 222, 128, 0.3)';
              }

              return (
                <motion.div
                  key={w.id}
                  initial={{ opacity: 0, x: 8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.2, delay: wIdx * 0.05 }}
                  style={{
                    background: 'rgba(255, 255, 255, 0.02)',
                    border: `1px solid ${borderColor}`,
                    borderRadius: 12,
                    padding: '12px 14px',
                    transition: 'all 0.2s ease',
                    minWidth: 0,
                    boxSizing: 'border-box'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6, gap: 8, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: 1 }}>
                      <span style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: w.status === 'active' ? '#38bdf8' : w.status === 'done' ? '#4ade80' : '#64748b',
                        flexShrink: 0
                      }} />
                      <span style={{ fontSize: 13, fontWeight: 800, color: '#FFFFFF', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{w.role}</span>
                    </div>
                    <span style={{
                      fontSize: 10,
                      fontWeight: 800,
                      textTransform: 'uppercase',
                      padding: '2px 7px',
                      borderRadius: 4,
                      background: statusBg,
                      color: statusColor,
                      flexShrink: 0,
                      marginLeft: 4
                    }}>
                      {w.status}
                    </span>
                  </div>

                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11.5, color: '#cbd5e1', paddingLeft: 16, overflowWrap: 'anywhere', wordBreak: 'break-word', minWidth: 0 }}>
                    {w.task}
                  </div>
                </motion.div>
              );
            })}
          </div>

        </div>

      </div>
    </section>
  );
}
