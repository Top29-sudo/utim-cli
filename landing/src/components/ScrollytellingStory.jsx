import React, { useState, useRef, useEffect } from 'react';
import { Copy, Check, Terminal, Sparkles, CheckCircle2, ArrowRight, Play, Cpu, ShieldCheck, Database, Layers } from 'lucide-react';
import { motion, useScroll, useSpring, AnimatePresence } from 'framer-motion';

export default function ScrollytellingStory() {
  const containerRef = useRef(null);
  const terminalRef = useRef(null);
  
  const [activeStep, setActiveStep] = useState(1);
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState('npm'); // 'npm' | 'pip' | 'source'
  const [selectedPrompt, setSelectedPrompt] = useState('stripe'); // 'stripe' | 'fastapi' | 'playwright' | 'rag'
  
  // 3D Tilt State
  const [rotateX, setRotateX] = useState(0);
  const [rotateY, setRotateY] = useState(0);

  // Global Page Scroll Progress for top bar
  const { scrollYProgress: globalScrollProgress } = useScroll();
  const scaleX = useSpring(globalScrollProgress, { stiffness: 100, damping: 30, restDelta: 0.001 });

  // Story Container Scroll Tracking
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"]
  });

  useEffect(() => {
    const unsubscribe = scrollYProgress.on("change", (latest) => {
      if (latest < 0.25) {
        setActiveStep(1);
      } else if (latest < 0.50) {
        setActiveStep(2);
      } else if (latest < 0.75) {
        setActiveStep(3);
      } else {
        setActiveStep(4);
      }
    });
    return () => unsubscribe();
  }, [scrollYProgress]);

  const installCommands = {
    npm: 'npm install -g @emend-ai/utim',
    pip: 'pip install utim',
    source: 'pip install ".[full]"'
  };

  const handleCopyCommand = () => {
    navigator.clipboard.writeText(installCommands[activeTab]);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Handle Mouse 3D Tilt on Terminal Canvas
  const handleMouseMove = (e) => {
    if (!terminalRef.current) return;
    const rect = terminalRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    
    // Subtle rotation between -4 and +4 degrees
    const rX = ((y - centerY) / centerY) * -4;
    const rY = ((x - centerX) / centerX) * 4;
    
    setRotateX(rX);
    setRotateY(rY);
  };

  const handleMouseLeave = () => {
    setRotateX(0);
    setRotateY(0);
  };

  const steps = [
    {
      num: 1,
      title: "1. One-Click Copy",
      desc: "Choose npm, pip, or full package and copy the global binary installation command to your clipboard."
    },
    {
      num: 2,
      title: "2. Open Local Terminal",
      desc: "Open your favorite terminal (pwsh, zsh, bash, tmux) directly inside your project workspace folder."
    },
    {
      num: 3,
      title: "3. Fast Dependency Install",
      desc: "UTIM installs in under 1.2s, registering the lightweight global CLI binary and stdio MCP daemon."
    },
    {
      num: 4,
      title: "4. Run 'utim' & Done",
      desc: "Provide any natural language prompt. UTIM plans steps, edits files, runs tests, and completes the task."
    }
  ];

  return (
    <>
      {/* Top Global Scroll Progress Bar */}
      <motion.div className="st-scroll-progress-bar" style={{ scaleX }} />

      {/* Hero Headline Section */}
      <section className="st-hero-section">
        <div className="st-hero-container">

          <h1 className="st-hero-title">
            You Think It, I Make It.
          </h1>

          <p className="st-hero-desc">
            The local-first autonomous developer agent for terminal-based software engineering. 
            Breaks tasks into steps, edits files, runs local commands, validates code, and keeps a reversible record of the work.
          </p>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, color: 'var(--text-muted)', fontSize: 13.5, fontWeight: 600 }}>
            <span>↓ Scroll down or interact with the terminal canvas below</span>
          </div>
        </div>
      </section>

      {/* True Pinned Scrollytelling Container */}
      <section className="st-scrolly-container" ref={containerRef} id="how-it-works" style={{ position: 'relative' }}>
        <div className="st-scrolly-sticky-stage">
          <div className="st-scrolly-grid">
            
            {/* Left Rail: 4-Step Progressive Story Stepper */}
            <div className="st-story-rail">
              {steps.map((s) => (
                <div
                  key={s.num}
                  className={`st-rail-step-card ${activeStep === s.num ? 'active' : ''}`}
                  onClick={() => setActiveStep(s.num)}
                >
                  <div className="st-step-card-header">
                    <span className="st-step-badge">{s.num}</span>
                    <h3 className="st-step-card-title">{s.title}</h3>
                  </div>
                  <p className="st-step-card-desc">{s.desc}</p>
                  {activeStep === s.num && (
                    <motion.div 
                      className="st-step-progress-line" 
                      layoutId="stepProgress" 
                      style={{ width: '100%' }}
                    />
                  )}
                </div>
              ))}
            </div>

            {/* Right Stage: Interactive Terminal Canvas with 3D Parallax & Mouse Interactivity */}
            <div 
              className="st-terminal-canvas-wrapper"
              onMouseMove={handleMouseMove}
              onMouseLeave={handleMouseLeave}
              ref={terminalRef}
            >
              <motion.div 
                className="st-terminal-showcase"
                animate={{ rotateX, rotateY }}
                transition={{ type: "spring", stiffness: 200, damping: 20 }}
              >
                {/* Terminal Window Header */}
                <div className="st-terminal-topbar">
                  <div className="st-term-dots">
                    <span className="st-dot st-dot-red"></span>
                    <span className="st-dot st-dot-yellow"></span>
                    <span className="st-dot st-dot-green"></span>
                  </div>
                  <div className="st-term-title">
                    {activeStep === 1 && "Step 1: Choose Distribution & Copy Command"}
                    {activeStep === 2 && "Step 2: Terminal Launch (~/projects/my-app)"}
                    {activeStep === 3 && "Step 3: Fast Package Installation (1.2s)"}
                    {activeStep === 4 && "Step 4: Autonomous CLI Execution (utim)"}
                  </div>
                  <div className="st-term-status">
                    <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', backgroundColor: '#4ADE80' }}></span>
                    READY
                  </div>
                </div>

                {/* Terminal Body with Dynamic Content based on Active Step */}
                <div className="st-terminal-body">
                  <AnimatePresence mode="wait">
                    {activeStep === 1 && (
                      <motion.div 
                        key="step1"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        transition={{ duration: 0.2 }}
                      >
                        <div style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
                          {['npm', 'pip', 'source'].map((tab) => (
                            <button
                              key={tab}
                              className={`st-term-prompt-chip ${activeTab === tab ? 'active' : ''}`}
                              onClick={() => setActiveTab(tab)}
                            >
                              {tab === 'npm' ? 'npm (Global)' : tab === 'pip' ? 'pip (Python 3.9+)' : 'pip full package'}
                            </button>
                          ))}
                        </div>

                        <div className="st-term-line st-term-dim"># Step 1: Copy global installation package</div>
                        <div className="st-term-line" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#1E222D', padding: '12px 18px', borderRadius: 8, border: '1px solid #334155', margin: '14px 0' }}>
                          <div>
                            <span className="st-term-green">developer@workstation</span>:<span className="st-term-cyan">~</span>$ <span className="st-term-cmd">{installCommands[activeTab]}</span>
                          </div>
                          <button 
                            onClick={handleCopyCommand}
                            style={{ background: copied ? '#059669' : '#334155', color: '#fff', border: 'none', padding: '6px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 700 }}
                          >
                            {copied ? <><Check size={14} /> Copied!</> : <><Copy size={14} /> Copy</>}
                          </button>
                        </div>

                        <div className="st-term-box">
                          <div className="st-term-box-header">📦 Package Manifest Information</div>
                          <div className="st-term-line">Distribution Target: Cross-Platform Native Binary</div>
                          <div className="st-term-line">Compatibility: Windows (PowerShell/CMD), macOS (Zsh/Bash), Linux, Termux</div>
                          <div className="st-term-line st-term-yellow">Includes: CLI TUI, Stdio MCP Manager, ChromaDB RAG, Vector Engine</div>
                        </div>
                        <div className="st-term-line st-term-dim">Scroll down or click Step 2 to continue the story...</div>
                      </motion.div>
                    )}

                    {activeStep === 2 && (
                      <motion.div 
                        key="step2"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        transition={{ duration: 0.2 }}
                      >
                        <div className="st-term-line st-term-dim"># Step 2: Open any native terminal in your repository</div>
                        <div className="st-term-line">
                          <span className="st-term-green">user@dev-machine</span>:<span className="st-term-cyan">~/projects</span>$ cd my-saas-app
                        </div>
                        <div className="st-term-line">
                          <span className="st-term-green">user@dev-machine</span>:<span className="st-term-cyan">~/projects/my-saas-app</span>$ pwd
                        </div>
                        <div className="st-term-line st-term-dim">/home/user/projects/my-saas-app</div>
                        
                        <div className="st-term-box">
                          <div className="st-term-box-header">⚡ Local-First Philosophy</div>
                          <div className="st-term-line">UTIM operates directly inside your local repository workspace.</div>
                          <div className="st-term-line">It inspects files, runs builds, and tests edits on your real machine.</div>
                          <div className="st-term-line st-term-cyan">Zero cloud lock-in. Full privacy and workspace security.</div>
                        </div>
                        <div className="st-term-line st-term-dim">Scroll down to observe package installation...</div>
                      </motion.div>
                    )}

                    {activeStep === 3 && (
                      <motion.div 
                        key="step3"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        transition={{ duration: 0.2 }}
                      >
                        <div className="st-term-line">
                          <span className="st-term-green">user@dev-machine</span>:<span className="st-term-cyan">~</span>$ {installCommands[activeTab]}
                        </div>
                        <div className="st-term-line st-term-dim">Resolving dependencies from registry...</div>
                        <div className="st-term-line st-term-green">✔ Downloaded utim-cli v2.1.3 (1.4 MB) in 420ms</div>
                        <div className="st-term-line st-term-green">✔ Verified SHA-256 integrity checksum</div>
                        <div className="st-term-line st-term-green">✔ Symlinked global binary: /usr/local/bin/utim &rarr; utim</div>

                        <div className="st-term-line st-term-cyan" style={{ marginTop: 14 }}>✨ Successfully installed UTIM AI CLI v2.1.3 in 1.2s!</div>
                        <div className="st-term-box">
                          <div className="st-term-line st-term-dim">You can now run "utim" from any terminal directory.</div>
                        </div>
                        <div className="st-term-line st-term-dim">Scroll down to see autonomous agent execution in action...</div>
                      </motion.div>
                    )}

                    {activeStep === 4 && (
                      <motion.div 
                        key="step4"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        transition={{ duration: 0.2 }}
                      >
                        {/* Interactive Prompt Switcher inside Step 4 */}
                        <div className="st-term-prompts-row">
                          <span style={{ fontSize: 11.5, color: '#94A3B8', display: 'flex', alignItems: 'center', marginRight: 4 }}>
                            Try Prompt:
                          </span>
                          <button 
                            className={`st-term-prompt-chip ${selectedPrompt === 'stripe' ? 'active' : ''}`}
                            onClick={() => setSelectedPrompt('stripe')}
                          >
                            Stripe Webhooks
                          </button>
                          <button 
                            className={`st-term-prompt-chip ${selectedPrompt === 'fastapi' ? 'active' : ''}`}
                            onClick={() => setSelectedPrompt('fastapi')}
                          >
                            FastAPI & Auth
                          </button>
                          <button 
                            className={`st-term-prompt-chip ${selectedPrompt === 'playwright' ? 'active' : ''}`}
                            onClick={() => setSelectedPrompt('playwright')}
                          >
                            Playwright QA
                          </button>
                          <button 
                            className={`st-term-prompt-chip ${selectedPrompt === 'rag' ? 'active' : ''}`}
                            onClick={() => setSelectedPrompt('rag')}
                          >
                            ChromaDB RAG
                          </button>
                        </div>

                        {selectedPrompt === 'stripe' && (
                          <div>
                            <div className="st-term-line">
                              <span className="st-term-green">user@dev-machine</span>:<span className="st-term-cyan">~/projects/my-saas-app</span>$ <span className="st-term-cmd">utim "Add Stripe webhook signature validation and recovery"</span>
                            </div>
                            <div className="st-term-box">
                              <div className="st-term-box-header">🤖 UTIM AUTONOMOUS AGENT ACTIVE</div>
                              <div className="st-term-line st-term-green">✔ Step 1: Inspected src/api/webhooks/stripe.ts (Found missing signing secret validation)</div>
                              <div className="st-term-line st-term-green">✔ Step 2: Patched src/api/webhooks/stripe.ts with signature verification</div>
                              <div className="st-term-line st-term-green">✔ Step 3: Executed: npm test tests/stripe.test.ts (All 8 tests passing)</div>
                              <div className="st-term-line st-term-green">✔ Step 4: Snapshotted session checkpoint (/undo available)</div>
                              <div className="st-term-line st-term-cyan" style={{ marginTop: 8 }}>✨ Task complete in 4.8s with 0 manual intervention required!</div>
                            </div>
                          </div>
                        )}

                        {selectedPrompt === 'fastapi' && (
                          <div>
                            <div className="st-term-line">
                              <span className="st-term-green">user@dev-machine</span>:<span className="st-term-cyan">~/projects/backend</span>$ <span className="st-term-cmd">utim "Generate FastAPI users router with JWT auth & Alembic migration"</span>
                            </div>
                            <div className="st-term-box">
                              <div className="st-term-box-header">🤖 UTIM AUTONOMOUS AGENT ACTIVE</div>
                              <div className="st-term-line st-term-green">✔ Step 1: Scaffolding app/routers/users.py with OAuth2 password bearer</div>
                              <div className="st-term-line st-term-green">✔ Step 2: Created SQLAlchemy User model in app/models/user.py</div>
                              <div className="st-term-line st-term-green">✔ Step 3: Executed: alembic revision --autogenerate -m "create users"</div>
                              <div className="st-term-line st-term-green">✔ Step 4: Executed: pytest tests/test_auth.py (100% test coverage)</div>
                              <div className="st-term-line st-term-cyan" style={{ marginTop: 8 }}>✨ Router generated and migrated in 5.2s!</div>
                            </div>
                          </div>
                        )}

                        {selectedPrompt === 'playwright' && (
                          <div>
                            <div className="st-term-line">
                              <span className="st-term-green">user@dev-machine</span>:<span className="st-term-cyan">~/projects/web</span>$ <span className="st-term-cmd">utim "Run Playwright visual regression tests and fix broken checkout CTA"</span>
                            </div>
                            <div className="st-term-box">
                              <div className="st-term-box-header">🤖 UTIM AUTONOMOUS AGENT ACTIVE</div>
                              <div className="st-term-line st-term-green">✔ Step 1: Spawning headless Chromium via MCP browser protocol</div>
                              <div className="st-term-line st-term-green">✔ Step 2: Captured screenshot diff on /checkout (Button overlap detected)</div>
                              <div className="st-term-line st-term-green">✔ Step 3: Adjusted flexbox z-index & padding in components/Checkout.tsx</div>
                              <div className="st-term-line st-term-green">✔ Step 4: Re-ran visual diff suite (0 regressions, test passed)</div>
                              <div className="st-term-line st-term-cyan" style={{ marginTop: 8 }}>✨ Visual QA resolved autonomously in 6.1s!</div>
                            </div>
                          </div>
                        )}

                        {selectedPrompt === 'rag' && (
                          <div>
                            <div className="st-term-line">
                              <span className="st-term-green">user@dev-machine</span>:<span className="st-term-cyan">~/projects/core</span>$ <span className="st-term-cmd">utim "Index project docs into ChromaDB and summarize billing architecture"</span>
                            </div>
                            <div className="st-term-box">
                              <div className="st-term-box-header">🤖 UTIM AUTONOMOUS AGENT ACTIVE</div>
                              <div className="st-term-line st-term-green">✔ Step 1: Parsed 42 Markdown & Python files across repository</div>
                              <div className="st-term-line st-term-green">✔ Step 2: Embedded 128 chunks into local .utim/chroma_db vector store</div>
                              <div className="st-term-line st-term-green">✔ Step 3: Retrieved billing architecture graph with 0 token waste</div>
                              <div className="st-term-line st-term-cyan" style={{ marginTop: 8 }}>✨ Vector memory indexed in 2.9s!</div>
                            </div>
                          </div>
                        )}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </motion.div>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
