import React, { useState } from 'react';
import { HelpCircle, ChevronDown, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const FAQS = [
  {
    q: 'How does UTIM CLI work in local repositories without an IDE plugin?',
    a: 'UTIM runs as a standalone, native global CLI binary (`utim`). It directly reads your workspace directory, utilizes ChromaDB local embeddings for repository symbol graphs, and executes terminal builds/tests while presenting clean Rich/Prompt_Toolkit interfaces in PowerShell, Bash, Zsh, or Tmux.'
  },
  {
    q: 'Can I use UTIM 100% for free?',
    a: 'Yes. UTIM includes a permanent Free Plan with 1,000 monthly credits and unlimited completion requests on free models (Cohere North Mini Code, Qwen 2.5 Coder 32B Free, Gemma 2 9B Instruct, and Nemotron Nano) with zero subscription fees required.'
  },
  {
    q: 'What is Bring Your Own Key (BYOK) mode?',
    a: 'With BYOK, you can provide your own custom OpenAI, Anthropic, Gemini, OpenRouter, or local Ollama API keys. When using BYOK, completion requests route directly through your keys and do not deduct any UTIM credits.'
  },
  {
    q: 'How do Model Context Protocol (MCP) servers integrate with UTIM?',
    a: 'UTIM natively supports the Model Context Protocol (stdio & SSE). You can attach PostgreSQL, SQLite, GitHub, Playwright browser QA, Figma, or custom local scripts. Agents inspect available MCP tools dynamically during the plan execution loop.'
  },
  {
    q: 'What makes UTIM different from Claude Code and Cursor?',
    a: 'Unlike single-vendor CLI tools, UTIM supports multi-model switching, native subagents, local ChromaDB semantic memory, an open Creators Miniagent Marketplace (with 95% revenue share for custom skills), and a reversible transaction log with `/undo` and `/rewind` commands.'
  },
  {
    q: 'How does the Creators Marketplace revenue share work?',
    a: 'Creators can build custom miniagents and workspace skills, package them with a `SKILL.md` and MCP hooks, and publish them to the UTIM Marketplace. Whenever developers install or use your paid agents, 95% of net royalties are paid directly to your creator account.'
  },
];

export default function InteractiveFaq() {
  const [openIndex, setOpenIndex] = useState(0);

  const toggle = (idx) => {
    setOpenIndex(openIndex === idx ? -1 : idx);
  };

  return (
    <section className="st-faq-section" style={{ padding: '80px 24px', background: 'var(--bg-cream-alt)', borderTop: '1px solid var(--border-cream)' }}>
      <div className="st-container" style={{ maxWidth: 840 }}>
        
        {/* Section Header */}
        <div className="st-section-header" style={{ marginBottom: 40 }}>
          <div className="st-hero-badge">
            <HelpCircle size={14} /> FREQUENTLY ASKED QUESTIONS
          </div>
          <h2 className="st-section-title">
            Everything You Need to Know
          </h2>
          <p className="st-section-subtitle">
            Clear answers on billing, local vector memory, BYOK mode, and MCP extensions.
          </p>
        </div>

        {/* Accordion List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {FAQS.map((faq, idx) => {
            const isOpen = openIndex === idx;
            return (
              <div
                key={idx}
                style={{
                  background: '#FFFFFF',
                  border: '1px solid var(--border-cream)',
                  borderRadius: 12,
                  overflow: 'hidden',
                  boxShadow: 'var(--shadow-xs)',
                  transition: 'all 0.15s ease'
                }}
              >
                <button
                  type="button"
                  onClick={() => toggle(idx)}
                  style={{
                    width: '100%',
                    padding: '18px 22px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 16,
                    background: 'transparent',
                    border: 'none',
                    textAlign: 'left',
                    cursor: 'pointer',
                    fontSize: '1.02rem',
                    fontWeight: 750,
                    color: 'var(--text-primary)'
                  }}
                >
                  <span>{faq.q}</span>
                  <ChevronDown
                    size={18}
                    style={{
                      transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                      transition: 'transform 0.2s ease',
                      flexShrink: 0,
                      color: 'var(--text-muted)'
                    }}
                  />
                </button>

                <AnimatePresence>
                  {isOpen && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                    >
                      <div style={{ padding: '0 22px 20px 22px', color: 'var(--text-secondary)', fontSize: '0.94rem', lineHeight: 1.65, borderTop: '1px solid var(--border-light)', paddingTop: 14 }}>
                        {faq.a}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </div>

      </div>
    </section>
  );
}
