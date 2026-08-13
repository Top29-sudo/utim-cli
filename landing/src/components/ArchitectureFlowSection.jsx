import React, { useState } from 'react';
import { 
  Cpu, Database, Terminal, RotateCcw, 
  Layers, ArrowRight, Shield, CheckCircle2,
  Sparkles, Code, GitBranch, Zap
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const NODES = [
  {
    id: 'planner',
    name: 'Checklist Planner & Subagents',
    tag: 'DYNAMIC TASK GRAPH',
    icon: Cpu,
    desc: 'Transforms high-level developer intentions into an atomic, structured task list. Spawns concurrent subagents for independent research, code editing, and test verification.',
    codeSnippet: `// Planner Step Execution Loop\nconst plan = await planner.breakdown(prompt);\nfor (const step of plan.steps) {\n  const result = await subagent.execute(step);\n  if (result.status === 'error') {\n    await selfHealing.remediate(result.error);\n  }\n}`
  },
  {
    id: 'memory',
    name: 'ChromaDB Vector Graph',
    tag: 'LOCAL SEMANTIC RAG',
    icon: Database,
    desc: 'Local ChromaDB vector database stores repository symbols, conventions, and project history. Automatically retrieves relevant AST nodes without bloating the token context window.',
    codeSnippet: `// Local Vector Search\nconst context = await chroma.query({\n  collection: "repo_symbols",\n  queryEmbeddings: embed(prompt),\n  nResults: 5,\n  where: { language: "typescript" }\n});`
  },
  {
    id: 'tools',
    name: 'MCP Protocol & Sandboxed CLI',
    tag: '200+ EXTENSIONS',
    icon: Layers,
    desc: 'Standard Model Context Protocol client connecting stdio & SSE servers. Direct access to GitHub PRs, Postgres queries, Playwright headless browsers, and safe local terminal commands.',
    codeSnippet: `// MCP Tool Call Dispatch\nconst toolResult = await mcpClient.call({\n  server: "postgres",\n  tool: "execute_query",\n  args: { sql: "SELECT * FROM users WHERE active = true" }\n});`
  },
  {
    id: 'snapshots',
    name: 'Reversible Diff & Snapshot Engine',
    tag: 'ATOMIC UNDO / REWIND',
    icon: RotateCcw,
    desc: 'Every file modification creates an atomic snapshot diff. Developers can instantly run `/undo` or `/rewind` to revert changes safely without messy git conflicts.',
    codeSnippet: `// Reversible Snapshot Rollback\nawait session.createCheckpoint("before_refactor");\n// If tests fail or user runs /undo:\nawait session.rollbackToCheckpoint("before_refactor");`
  }
];

export default function ArchitectureFlowSection() {
  const [selectedNode, setSelectedNode] = useState(NODES[0]);

  return (
    <section className="st-features-section" style={{ padding: '80px 24px', background: 'var(--bg-cream-alt)', borderTop: '1px solid var(--border-cream)', borderBottom: '1px solid var(--border-cream)', position: 'relative' }}>
      <div className="st-container">
        
        {/* Header with Scroll Trigger */}
        <motion.div 
          initial={{ opacity: 0, y: 22 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.38, ease: [0.16, 1, 0.3, 1] }}
          className="st-section-header" 
          style={{ marginBottom: 44 }}
        >
          <div className="st-hero-badge">
            <Shield size={13} /> Local-first architecture
          </div>
          <h2 className="st-section-title">
            How UTIM Operates Under the Hood
          </h2>
          <p className="st-section-subtitle">
            An open, deterministic system designed for safety, local vector recall, and complete transparency.
          </p>
        </motion.div>

        {/* Interactive Flow Diagram with Stagger Animation */}
        <div className="st-arch-flow-grid">
          {NODES.map((n, idx) => {
            const isSelected = n.id === selectedNode.id;
            const Icon = n.icon;
            return (
              <motion.div
                key={n.id}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-60px' }}
                transition={{ duration: 0.35, delay: idx * 0.06, ease: [0.16, 1, 0.3, 1] }}
                onClick={() => setSelectedNode(n)}
                style={{
                  background: isSelected ? 'var(--accent-black)' : '#FFFFFF',
                  color: isSelected ? '#FFFFFF' : 'var(--text-primary)',
                  border: isSelected ? '1px solid var(--accent-black)' : '1px solid var(--border-cream)',
                  borderRadius: 14,
                  padding: '20px 22px',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  boxShadow: isSelected ? 'var(--shadow-md)' : 'var(--shadow-xs)',
                  position: 'relative'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                  <div style={{
                    width: 38,
                    height: 38,
                    borderRadius: 10,
                    background: isSelected ? 'rgba(255, 255, 255, 0.15)' : 'var(--bg-cream)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: isSelected ? '#FFFFFF' : 'var(--text-primary)'
                  }}>
                    <Icon size={20} />
                  </div>
                  <span style={{ fontSize: 11, fontWeight: 800, color: isSelected ? '#94a3b8' : 'var(--text-muted)' }}>
                    0{idx + 1}
                  </span>
                </div>

                <div style={{ fontSize: 11.5, fontWeight: 600, color: isSelected ? 'var(--term-cyan)' : 'var(--text-secondary)', textTransform: 'none', letterSpacing: '0.02em', marginBottom: 4 }}>
                  {n.tag}
                </div>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: 16.5, fontWeight: 600, lineHeight: 1.3 }}>
                  {n.name}
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Selected Node Deep Dive Workbench with Scroll Animation */}
        <motion.div 
          initial={{ opacity: 0, y: 24, scale: 0.98 }}
          whileInView={{ opacity: 1, y: 0, scale: 1 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.42, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="st-arch-workbench-card"
        >
          <div>
            <div style={{ display: 'inline-block', fontSize: 12, fontWeight: 800, color: 'var(--accent-black)', background: 'var(--bg-cream)', padding: '4px 10px', borderRadius: 6, marginBottom: 14 }}>
              {selectedNode.tag}
            </div>
            <h3 style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: 12, letterSpacing: '-0.02em' }}>
              {selectedNode.name}
            </h3>
            <p style={{ fontSize: '1rem', color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: 20 }}>
              {selectedNode.desc}
            </p>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 650, color: 'var(--text-primary)' }}>
                <CheckCircle2 size={16} color="#059669" /> Zero cloud telemetry lock-in
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 650, color: 'var(--text-primary)' }}>
                <CheckCircle2 size={16} color="#059669" /> 100% deterministic local control
              </span>
            </div>
          </div>

          {/* Code Engine Preview */}
          <div style={{
            background: '#0e0e11',
            borderRadius: 12,
            border: '1px solid #27272a',
            overflow: 'hidden',
            fontFamily: "'JetBrains Mono', monospace"
          }}>
            <div style={{
              background: '#18181b',
              padding: '10px 16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderBottom: '1px solid #27272a',
              fontSize: 12,
              color: '#a1a1aa'
            }}>
              <span>engine/{selectedNode.id}.ts</span>
              <span style={{ color: '#4ade80' }}>EXECUTABLE SPEC</span>
            </div>
            <pre style={{
              padding: '18px 20px',
              margin: 0,
              fontSize: 12.5,
              lineHeight: 1.65,
              color: '#e4e4e7',
              overflowX: 'auto'
            }}>
              <code>{selectedNode.codeSnippet}</code>
            </pre>
          </div>
        </motion.div>

      </div>
    </section>
  );
}
