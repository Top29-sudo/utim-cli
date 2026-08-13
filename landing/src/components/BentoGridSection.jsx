import React, { useState, useEffect } from 'react';
import { 
  Sparkles, Bot, Key, DollarSign, 
  RotateCcw, History, Compass, Database, 
  FileCode, Share2, Layers, Gift, 
  ChevronDown, ChevronUp, CheckCircle 
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { getApiUrl } from '../lib/api';

export default function BentoGridSection() {
  const [showModels, setShowModels] = useState(false);
  const [freeModels, setFreeModels] = useState([
    "cohere/north-mini-code:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "inclusionai/ling-3.0-flash:free",
    "poolside/laguna-s-2.1:free",
    "openai/gpt-oss-20b:free",
    "poolside/laguna-m.1:free"
  ]);

  const [paidModelsPreview, setPaidModelsPreview] = useState([
    "anthropic/claude-opus-5",
    "anthropic/claude-sonnet-5",
    "anthropic/claude-sonnet-4.6",
    "openai/gpt-5.6-sol-pro",
    "openai/gpt-5.3-codex",
    "deepseek/deepseek-v4-pro",
    "google/gemini-3.6-flash",
    "qwen/qwen3.8-max"
  ]);

  useEffect(() => {
    async function fetchServerModels() {
      try {
        const apiUrl = getApiUrl();
        const res = await fetch(`${apiUrl}/api/models`);
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            const fetchedFree = data.filter(m => m.is_free || m.model_id.endsWith(':free')).map(m => m.model_id);
            const fetchedPaid = data.filter(m => !m.is_free && !m.model_id.endsWith(':free')).map(m => m.model_id);
            if (fetchedFree.length > 0) setFreeModels(fetchedFree);
            if (fetchedPaid.length > 0) setPaidModelsPreview(fetchedPaid);
          }
        }
      } catch (err) {
        console.warn('Using verified fallback server models in BentoGrid:', err);
      }
    }
    fetchServerModels();
  }, []);

  // Exact 10 features as specified in features.md
  const features = [
    {
      num: "01",
      title: "100% Terminal-Native",
      desc: "Zero browser lock-in, zero cloud IDE dependency. Run entire AI engineering workflows right inside PowerShell, Bash, Zsh, or Windows Terminal with rich TUI formatting.",
      tags: ["PowerShell", "Bash", "Zsh", "Terminal"],
      icon: Layers,
      span: "st-bento-span-2"
    },
    {
      num: "02",
      title: "Model Context Protocol (MCP)",
      desc: "Connect local and remote tools seamlessly via MCP stdio/SSE protocol. Native integrations for Postgres, GitHub, Puppeteer, Docker, and 200+ community extensions.",
      tags: ["MCP Stdio", "SSE", "200+ Tools"],
      icon: Database,
      span: ""
    },
    {
      num: "03",
      title: "Reversible History Snapshots",
      desc: "Atomic session checkpoints allow instant rollback with `/undo` and `/rewind`. Multi-turn session branching gives you complete safety when experimenting.",
      tags: ["/undo", "/rewind", "Zero Git Mess"],
      icon: RotateCcw,
      span: ""
    },
    {
      num: "04",
      title: "Task Planner & Subagents",
      desc: "Automatic task breakdown with real-time checklist UI. Spawns specialized background subagents to work concurrently on multi-file features and research.",
      tags: ["/plan", "Subagents", "Async Engine"],
      icon: Compass,
      span: "st-bento-span-2"
    },
    {
      num: "05",
      title: "Real-time Token Compute & Costs",
      desc: "Live token counter, execution time, and credit consumption calculated per turn. Complete visibility into prompt caching and model efficiency.",
      tags: ["Token Counter", "/cost", "Transparent"],
      icon: DollarSign,
      span: ""
    },
    {
      num: "06",
      title: "Creators Marketplace (95% Rev Share)",
      desc: "Publish custom miniagents and tools. Earn 95% revenue share on every execution credit spent by developers worldwide.",
      tags: ["95% Payout", "Miniagents", "Ecosystem"],
      icon: Sparkles,
      span: ""
    },
    {
      num: "07",
      title: "Bring Your Own Key (BYOK)",
      desc: "Connect any OpenAI-compatible provider using your own API keys. BYOK models bypass UTIM quota limits entirely and persist across project folders automatically.",
      tags: ["BYOK", "Custom Models", "No Limits"],
      icon: Key,
      span: ""
    },
    {
      num: "08",
      title: "Instant Workspace Sharing",
      desc: "Instantly zip and share your workspace, session history, and conversation context with teammates. Secure shareable links generated from the CLI in one command.",
      tags: ["/share", "Zip Export", "Team Link"],
      icon: Share2,
      span: ""
    },
    {
      num: "09",
      title: "Workspace Custom Skills (SKILL.md)",
      desc: "Auto-embed local SKILL.md guidelines into your context via local ChromaDB RAG. Saves prompt tokens and gives UTIM context-aware project rules without re-prompting.",
      tags: ["SKILL.md", "AGENTS.md", "Rules"],
      icon: FileCode,
      span: ""
    },
    {
      num: "10",
      title: "Quota Sharing & Redeem Codes",
      desc: "Share your rollover Quota Bank and regular subscription credits with your referred teammates directly from the CLI, or generate non-expiring, secure redeem codes to distribute or claim later.",
      tags: ["/quotashare", "/redeem", "Collaboration"],
      icon: Gift,
      span: "st-bento-span-2"
    }
  ];

  return (
    <section className="st-features-section" style={{ padding: '80px 24px', background: 'var(--bg-cream-alt)' }}>
      <div className="st-container">
        
        {/* Section Header with Scroll Trigger */}
        <motion.div 
          initial={{ opacity: 0, y: 22 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.38, ease: [0.16, 1, 0.3, 1] }}
          className="st-section-header"
        >
          <h2 className="st-section-title">
            Engineered for Autonomous Engineering
          </h2>
          <p className="st-section-subtitle">
            Explore the complete feature matrix built natively into the UTIM CLI ecosystem.
          </p>
        </motion.div>

        {/* Bento Grid Layout with Fast Stagger */}
        <div className="st-bento-grid">
          {features.map((f, idx) => {
            const IconComponent = f.icon;
            return (
              <motion.div 
                key={f.num} 
                className={`st-bento-card ${f.span}`}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-40px' }}
                transition={{ duration: 0.32, delay: (idx % 4) * 0.05, ease: [0.16, 1, 0.3, 1] }}
                whileHover={{ y: -4, transition: { duration: 0.15 } }}
              >
                <div className="st-card-top-row">
                  <div className="st-card-icon-box">
                    <IconComponent size={24} />
                  </div>
                  <span className="st-feature-index">{f.num}</span>
                </div>
                <h3 className="st-card-title">{f.title}</h3>
                <p className="st-card-desc">{f.desc}</p>
                <div className="st-tags-list">
                  {f.tags.map((tag, tIdx) => (
                    <span key={tIdx} className="st-tag-item">{tag}</span>
                  ))}
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Models and Providers Accordion with Scroll Animation */}
        <motion.div 
          className="st-models-catalog-box"
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.4, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
        >
          <div 
            className="st-models-catalog-header"
            onClick={() => setShowModels(!showModels)}
          >
            <div className="st-models-title">
              <Bot size={24} />
              <span>11 Models &amp; Providers Catalog</span>
            </div>
            <button className="st-install-tab active" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              {showModels ? (
                <><span>Hide Model Registry</span><ChevronUp size={16} /></>
              ) : (
                <><span>View All Models</span><ChevronDown size={16} /></>
              )}
            </button>
          </div>

          <p style={{ fontSize: '1rem', color: 'var(--text-body)', lineHeight: 1.7 }}>
            UTIM provides a comprehensive registry of official AI models. Free-tier models are priced at just <strong>$0.02 in / $0.03 out per 1M tokens</strong> for Free users, with a <strong>10x priority discount ($0.002 in / $0.003 out per 1M tokens)</strong> for all Paid subscribers. Full support for Bring-Your-Own-Key (BYOK) endpoints and separate model routing for main and background subagents.
          </p>

          <AnimatePresence>
            {showModels && (
              <motion.div 
                className="st-models-grid"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.25 }}
              >
                <div className="st-model-category-card">
                  <h4 className="st-model-category-title">Free Tier Models</h4>
                  <ul className="st-model-items-list">
                    {freeModels.map((m, i) => (
                      <li key={i}>{m}</li>
                    ))}
                  </ul>
                </div>

                <div className="st-model-category-card">
                  <h4 className="st-model-category-title">Paid Tier Models (Hobby / Pro / Max / Ultimate)</h4>
                  <ul className="st-model-items-list">
                    {paidModelsPreview.map((m, i) => (
                      <li key={i}>{m}</li>
                    ))}
                    <li style={{ color: 'var(--text-muted)' }}>+ 50 more premium vision &amp; code models in CLI</li>
                  </ul>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </section>
  );
}
