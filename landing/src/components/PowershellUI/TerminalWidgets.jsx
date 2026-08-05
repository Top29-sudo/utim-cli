import React, { useState, useEffect } from 'react';
import { getApiUrl } from '../../lib/api';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import ReactMarkdown from 'react-markdown';
import docsMd from '../../docs_md/docs.md?raw';
import privacyMd from '../../docs_md/privacy.md?raw';
import termsMd from '../../docs_md/terms.md?raw';
import licenseMd from '../../docs_md/license.md?raw';
import refundMd from '../../docs_md/refund.md?raw';
import './TerminalWidgets.css';
import CreditTopup from '../CreditTopup';
import changelogMd from '../../docs_md/changelog.md?raw';

import featuresMd from '../../docs_md/features.md?raw';

const detectIsIndian = () => {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (tz && (tz.toLowerCase().includes('kolkata') || tz.toLowerCase().includes('calcutta'))) {
      return true;
    }
    const locale = navigator.language || '';
    if (locale.toLowerCase().includes('-in')) {
      return true;
    }
    if (navigator.languages && navigator.languages.some(l => l.toLowerCase().includes('-in'))) {
      return true;
    }
  } catch (e) {}
  return false;
};

const featuresData = [
  { 
    id: "loop", number: "01", title: "Autonomous Agent Loop", 
    desc: "Think-act-observe cycle with structured checklist planning. UTIM breaks tasks into steps, executes code, runs builds, and self-heals failures — all without lifting a finger.", 
    color: "#E5FF00",
    icon: "⟳",
    tags: ["Planning", "Self-healing", "Auto-accept"]
  },
  { 
    id: "terminal", number: "02", title: "Full System Control", 
    desc: "Runs shell commands, installs packages, spawns dev servers, and reads/writes your entire codebase directly on your machine. Dry-run & sandbox mode for safe exploration.", 
    color: "#00F0FF",
    icon: ">_",
    tags: ["Shell", "Sandbox", "Dry-run"]
  },
  { 
    id: "vision", number: "03", title: "Visual Analysis Engine", 
    desc: "Analyzes screenshots and images using vision AI. Detects layout bugs, UI inconsistencies, and generates assets via AI image generation — all from the CLI.", 
    color: "#FF66B2",
    icon: "◎",
    tags: ["Screenshots", "Image Gen", "UI QA"]
  },
  { 
    id: "memory", number: "04", title: "Semantic Vector Memory", 
    desc: "ChromaDB-backed RAG memory stores facts, conventions, and project history. Relevant context is automatically embedded into the prompt — no more re-explaining your stack.", 
    color: "#B266FF",
    icon: "⬡",
    tags: ["ChromaDB", "RAG", "Embeddings"]
  },
  { 
    id: "revert", number: "05", title: "Undo / Redo / Rewind", 
    desc: "Every file change is diffed and snapshotted to session state. Roll back any edit, redo it, or rewind to any conversation turn — even after restarting your machine.", 
    color: "#FF8C00",
    icon: "↩",
    tags: ["/undo", "/rewind", "Diff snapshots"]
  },
  { 
    id: "mcp", number: "06", title: "MCP Tool Ecosystem", 
    desc: "Connects to any Model Context Protocol server — databases, GitHub, Figma, Slack, Playwright browser automation — with a curated registry of 200+ pre-configured servers.", 
    color: "#00FF66",
    icon: "⊕",
    tags: ["MCP", "Playwright", "GitHub"]
  },
  { 
    id: "byok", number: "07", title: "Bring Your Own Key", 
    desc: "Connect any OpenAI-compatible provider using your own API keys. BYOK models bypass UTIM quota limits entirely and persist across project folders automatically.", 
    color: "#FFA500",
    icon: "⚿",
    tags: ["BYOK", "Custom Models", "No Limits"]
  },
  { 
    id: "share", number: "08", title: "Share & Collaborate", 
    desc: "Instantly zip and share your workspace, session history, and conversation context with teammates. Secure shareable links generated from the CLI in one command.", 
    color: "#5ba3c9",
    icon: "⇗",
    tags: ["/share", "Zip Export", "Team Link"]
  },
  { 
    id: "skills", number: "09", title: "Workspace Custom Skills", 
    desc: "Auto-embed local SKILL.md guidelines into your context via local ChromaDB RAG. Saves prompt tokens and gives UTIM context-aware project rules without re-prompting.", 
    color: "#FF4C8B",
    icon: "★",
    tags: ["SKILL.md", "AGENTS.md", "Rules"]
  },
  {
    id: "quotashare", number: "10", title: "Quota Sharing & Redeem",
    desc: "Share your rollover Quota Bank and regular subscription credits with your referred teammates directly from the CLI, or generate non-expiring, secure redeem codes to distribute or claim later.",
    color: "#C084FC",
    icon: "🎟️",
    tags: ["/quotashare", "/redeem", "Collaboration"]
  },
  {
    id: "marketplace", number: "11", title: "Creators Ecosystem",
    desc: "Global marketplace to browse, download, install, purchase, and publish custom skills and script-based miniagents with built-in publisher profiles, wallet earnings, and withdrawal payouts.",
    color: "#cba6f7",
    icon: "🏪",
    tags: ["/marketplace", "Skills", "Miniagents", "Publish & Earn"]
  }
];

export const InlineFeatures = () => {
  return (
    <div className="term-markdown-view">
      <motion.div 
        className="term-md-header"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="term-md-tag">[CAPABILITIES • AUTONOMOUS DEVELOPER ENGINE]</div>
        <div className="term-md-title"># U.T.I.M Core Capabilities</div>
        <div className="term-md-subtitle">
          The autonomous coding agent that reads your codebase, runs your shell, fixes its own bugs, and remembers everything — locally on your machine.
        </div>
      </motion.div>

      <div className="term-md-divider">================================================================================</div>

      {/* 3-column card grid matching site aesthetic */}
      <div className="tw-features-grid-massive">
        {featuresData.map((f, i) => (
          <motion.div 
            key={f.id} 
            className="tw-feature-card-large"
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.07, type: 'spring', stiffness: 120, damping: 14 }}
            style={{ '--glow-color': f.color }}
          >
            {/* Icon banner */}
            <div style={{
              width: '100%',
              height: '90px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: `radial-gradient(ellipse at 50% 0%, ${f.color}18 0%, transparent 75%)`,
              borderRadius: '8px',
              marginBottom: '20px',
              border: `1px solid ${f.color}22`,
              fontSize: '2.4rem',
              fontFamily: 'monospace',
              color: f.color,
              letterSpacing: '-1px',
              userSelect: 'none'
            }}>
              {f.icon}
            </div>

            <div className="tw-feature-content-large">
              <div className="tw-feature-num-large" style={{ color: f.color }}>{f.number}</div>
              <h3 className="tw-feature-name-large">{f.title}</h3>
              <p className="tw-feature-desc-large">{f.desc}</p>
              <div className="tw-feature-tags">
                {f.tags.map(t => (
                  <span key={t} className="tw-feature-tag" style={{ borderColor: f.color, color: f.color }}>{t}</span>
                ))}
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export const parseChangelogMarkdown = (mdText) => {
  if (!mdText) return [];
  const lines = mdText.split('\n');
  const versions = [];
  let currentVersion = null;
  let currentGroup = null;

  const typeMap = {
    'added': 'feature',
    'changed': 'update',
    'fixed': 'fix',
    'security': 'security'
  };

  for (let line of lines) {
    line = line.trim();
    if (!line) continue;

    const verMatch = line.match(/^##\s+\[?([0-9a-zA-Z\.\-]+)\]?\s*-\s*([0-9]{4}-[0-9]{2}-[0-9]{2})/);
    if (verMatch) {
      const versionStr = verMatch[1];
      const dateStr = verMatch[2];
      
      let formattedDate = dateStr;
      try {
        const dateObj = new Date(dateStr + 'T00:00:00');
        if (!isNaN(dateObj.getTime())) {
          formattedDate = dateObj.toLocaleDateString('en-US', {
            month: 'long',
            day: 'numeric',
            year: 'numeric'
          });
        }
      } catch (e) {}

      currentVersion = {
        version: versionStr,
        date: formattedDate,
        changes: []
      };
      versions.push(currentVersion);
      currentGroup = null;
      continue;
    }

    const groupMatch = line.match(/^###\s+(.+)$/);
    if (groupMatch && currentVersion) {
      const groupName = groupMatch[1].toLowerCase().trim();
      const groupType = typeMap[groupName] || 'update';
      currentGroup = {
        type: groupType,
        items: []
      };
      currentVersion.changes.push(currentGroup);
      continue;
    }

    const itemMatch = line.match(/^[\-\*]\s+(.+)$/);
    if (itemMatch && currentVersion) {
      if (!currentGroup) {
        currentGroup = {
          type: 'update',
          items: []
        };
        currentVersion.changes.push(currentGroup);
      }
      let itemText = itemMatch[1];
      itemText = itemText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      currentGroup.items.push(itemText);
    }
  }

  return versions;
};

export const InlineChangelog = () => {
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchChangelog = async () => {
      try {
        const response = await fetch(`${getApiUrl()}/api/releases`).catch(() => null);
        if (response && response.ok) {
          const data = await response.json();
          if (Array.isArray(data) && data.length > 0) {
            setVersions(data);
            setLoading(false);
            return;
          }
        }
      } catch (err) {
        console.error('Error fetching changelog from server:', err);
      }

      // Fallback: dynamically parse client-compiled changelog.md raw file contents
      try {
        const parsed = parseChangelogMarkdown(changelogMd);
        if (parsed.length > 0) {
          setVersions(parsed);
        } else {
          throw new Error('Changelog parsing empty');
        }
      } catch (err) {
        console.error('Error parsing local changelog:', err);
        setError('Failed to parse release history.');
      } finally {
        setLoading(false);
      }
    };
    fetchChangelog();
  }, []);

  return (
    <div className="term-markdown-view">
      <motion.div 
        className="term-md-header"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="term-md-tag">[SYSTEM • VERSION HISTORY]</div>
        <div className="term-md-title"># UTIM CLI Agent Changelog</div>
        <div className="term-md-subtitle">
          Live changelog feed fetched directly from the Railway control server.
        </div>
      </motion.div>

      <div className="term-md-divider">================================================================================</div>

      {loading && (
        <div style={{ fontFamily: 'monospace', color: '#888', fontSize: '0.85rem' }}>
          Decrypting release notes from server...
        </div>
      )}

      {error && !versions.length && (
        <div style={{ fontFamily: 'monospace', color: '#ff6b6b', fontSize: '0.85rem' }}>
          [ERROR] Failed to fetch live changelog from Railway.
        </div>
      )}

      {!loading && !error && versions.map((ver, idx) => (
        <motion.div 
          key={idx} 
          style={{ marginBottom: '28px', fontFamily: 'monospace' }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: idx * 0.1 }}
        >
          <div style={{ color: '#00F0FF', fontWeight: 'bold', fontSize: '0.95rem' }}>
            ## [v{ver.version}] - {ver.date}
          </div>
          <div style={{ margin: '8px 0 0 16px' }}>
            {ver.changes.map((group, gIdx) => (
              <div key={gIdx} style={{ marginBottom: '12px' }}>
                <div style={{ color: '#E5FF00', textTransform: 'uppercase', fontSize: '0.8rem', fontWeight: 'bold' }}>
                  ### {group.type}:
                </div>
                <ul style={{ margin: '4px 0 0 16px', padding: 0, color: '#ccc', listStyleType: 'square', fontSize: '0.85rem', lineHeight: '1.5' }}>
                  {group.items.map((item, iIdx) => (
                    <li 
                      key={iIdx} 
                      style={{ marginBottom: '4px' }} 
                      dangerouslySetInnerHTML={{ __html: item.replace(/\n$/, '') }} 
                    />
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </motion.div>
      ))}
    </div>
  );
};

export const InlinePricing = () => {
  const navigate = useNavigate();
  const { user, getToken, refreshProfile, isAuthenticated } = useAuth();
  const [isUpdating, setIsUpdating] = useState(false);
  const [billingPeriod, setBillingPeriod] = useState('monthly');
  const [message, setMessage] = useState('');
  const [activePlanId, setActivePlanId] = useState(null);
  const [isIndian, setIsIndian] = useState(detectIsIndian());
  const [referralDiscounts, setReferralDiscounts] = useState({});

  // Dynamically detect user country via GeoIP with timezone fallback
  useEffect(() => {
    fetch('https://ipapi.co/json/')
      .then(res => res.json())
      .then(data => {
        if (data && data.country_code) {
          setIsIndian(data.country_code === 'IN');
        }
      })
      .catch(() => {});
  }, []);

  // Fetch referral discounts for the logged-in user
  useEffect(() => {
    if (!user) return;
    const fetchDiscounts = async () => {
      try {
        const token  = await getToken();
        const apiUrl = getApiUrl();
        const res    = await fetch(`${apiUrl}/api/referrals/info`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setReferralDiscounts(data.discounts || {});
        }
      } catch (_) {}
    };
    fetchDiscounts();
  }, [user]);

  // INR raw numbers for discount math
  const inrRaw = { hobby: 700, starter: 2500, professional: 5500, ultimate: 11000 };
  const usdRaw = { hobby: 7, starter: 25, professional: 55, ultimate: 110 };

  const getDiscountedPrice = (t) => {
    // Map frontend ID to backend ID
    const backendIdMap = {
      hobby: 'hobby',
      starter: 'pro',
      professional: 'max',
      ultimate: 'ultimate'
    };
    const dbId = backendIdMap[t.id] || t.id;
    const pct = referralDiscounts[dbId] || 0;
    if (!pct || t.id === 'free') return null;
    const capped = Math.min(100, pct);
    if (isIndian) {
      const orig = inrRaw[t.id];
      const disc = Math.round(orig * (1 - capped / 100));
      return { orig: `Rs. ${orig}/mo`, discounted: disc === 0 ? 'FREE' : `Rs. ${disc}/mo`, pct: capped };
    }
    const orig = usdRaw[t.id];
    const disc  = +(orig * (1 - capped / 100)).toFixed(2);
    return { orig: `$${orig}/mo`, discounted: disc === 0 ? 'FREE' : `$${disc}/mo`, pct: capped };
  };

  const getDisplayPrice = (t) => {
    if (t.id === 'free') return '$0';
    if (isIndian) {
      const inrPrices = {
        hobby: 'Rs. 700',
        starter: 'Rs. 2500',
        professional: 'Rs. 5500',
        ultimate: 'Rs. 11000'
      };
      return `${inrPrices[t.id]}/mo`;
    }
    return `${t.price}/mo`;
  };

  const getSavingsText = (t) => {
    return null;
  };

  // Dynamically load Razorpay SDK
  useEffect(() => {
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.async = true;
    document.body.appendChild(script);
    
    return () => {
      try {
        document.body.removeChild(script);
      } catch (e) {}
    };
  }, []);

  const tiers = [
    {
      id: "free",
      num: "01",
      name: "Free Node",
      price: "$0",
      sub: "/mo",
      color: "#888888",
      features: [
        "100 Credits refilled every 5 hours",
        "Monthly 3,000 credits limit (no quota bank)",
        "Free-tier models only (cohere, nvidia, qwen)",
        "Web search & codebase queries (non-agentic only)",
        "Agentic tools & Blender 3D model builder disabled",
        "Community support (Discord)"
      ]
    },
    {
      id: "hobby",
      num: "02",
      name: "Hobbyist Node",
      price: "$7",
      sub: "/mo",
      color: "#ec4899",
      features: [
        "4,000 Monthly Credits (+500 bonus credits on first purchase)",
        "Hobby-tier MoEs (deepseek-r1, kimi-k2.7)",
        "Agentic tools enabled (Analyse Image, Web Search, Codebase)",
        "Blender & 3D model tools disabled (requires Starter plan)",
        "ChromaDB experience database auto-sync",
        "Standard email support (48h SLA)"
      ]
    },
    {
      id: "starter",
      num: "03",
      name: "Starter Node",
      price: "$25",
      sub: "/mo",
      color: "#00F0FF",
      features: [
        "18,000 Monthly Credits (+2,000 bonus credits on first purchase)",
        "Pro-tier reasoning (claude-3.5, gemini-3.5)",
        "Blender & 3D model tools enabled (Tripo 3D models)",
        "Agentic tools enabled (Analyse Image, Web Search, Codebase)",
        "Custom Model Context Protocol (MCP) servers",
        "Developer support SLA (24h SLA)"
      ]
    },
    {
      id: "professional",
      num: "04",
      name: "Professional Core",
      price: "$55",
      sub: "/mo",
      color: "#e8c97a",
      features: [
        "45,000 Monthly Credits (+5,000 bonus credits on first purchase)",
        "All premium reasoning & visual models",
        "Mini-agents & visual layout QA",
        "Blender & 3D model tools enabled (Tripo 3D models)",
        "Priority support SLA (12h SLA)"
      ]
    },
    {
      id: "ultimate",
      num: "05",
      name: "MAX Node",
      price: "$110",
      sub: "/mo",
      color: "#00FF66",
      features: [
        "90,000 Monthly Credits (+12,000 bonus credits on first purchase)",
        "Unlimited project exports & storage",
        "Unlimited local vector memory database",
        "Elite visual QA & regression testing loops",
        "Blender & 3D model tools enabled (Tripo 3D models)",
        "Dedicated engineer support (1h SLA)"
      ]
    }
  ];

  const handleActivate = async (t) => {
    if (t.id === 'free') {
      if (!isAuthenticated || !user) {
        navigate('/auth?mode=signup&callback=/');
      } else {
        navigate('/');
      }
      return;
    }

    if (!isAuthenticated || !user) {
      navigate(`/auth?callback=${window.location.pathname}`);
      return;
    }

    setIsUpdating(true);
    setActivePlanId(t.id);
    setMessage(`Connecting to node ${t.name.toUpperCase()}...`);

    try {
      const token = await getToken();
      const apiUrl = getApiUrl();
      
      const response = await fetch(`${apiUrl}/api/subscription/create`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ 
          plan: t.id, 
          interval: 'monthly',
          currency: isIndian ? 'INR' : 'USD'
        })
      });
      
      const data = await response.json();
      
      if (data.success && data.subscriptionId) {
        if (data.subscriptionId.startsWith('free_referral_100pct') || data.keyId === 'free') {
          try {
            setMessage('Verifying free subscription quota...');
            const verifyRes = await fetch(`${apiUrl}/api/subscription/verify`, {
              method: 'POST',
              headers: { 
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json' 
              },
              body: JSON.stringify({
                razorpay_subscription_id: data.subscriptionId,
                razorpay_payment_id: 'pay_free',
                razorpay_signature: 'sig_free'
              })
            });
            const verifyData = await verifyRes.json();
            if (verifyData.success) {
              setMessage(`SUCCESS: Node reconfigured to ${t.name} (Free Referral Reward Active!)`);
              await refreshProfile();
            } else {
              setMessage(`ERROR: ${verifyData.error || 'Subscription verification failed'}`);
            }
          } catch (err) {
            setMessage('ERROR: Network failure during verification');
          } finally {
            setIsUpdating(false);
          }
          return;
        }

        const options = {
          key: data.keyId,
          subscription_id: data.subscriptionId,
          name: 'U.T.I.M AI',
          description: `${t.name} Subscription (Autopay)`,
          handler: async function (response) {
            try {
              setMessage('Verifying subscription signature...');
              const verifyRes = await fetch(`${apiUrl}/api/subscription/verify`, {
                method: 'POST',
                headers: { 
                  'Authorization': `Bearer ${token}`,
                  'Content-Type': 'application/json' 
                },
                body: JSON.stringify({
                  razorpay_subscription_id: response.razorpay_subscription_id,
                  razorpay_payment_id: response.razorpay_payment_id,
                  razorpay_signature: response.razorpay_signature
                })
              });
              const verifyData = await verifyRes.json();
              if (verifyData.success) {
                setMessage(`SUCCESS: Node reconfigured to ${t.name} (Autopay Active)`);
                await refreshProfile();
              } else {
                setMessage(`ERROR: ${verifyData.error || 'Subscription verification failed'}`);
              }
            } catch (err) {
              setMessage('ERROR: Network failure during verification');
            } finally {
              setIsUpdating(false);
            }
          },
          prefill: {
            email: user.email || ''
          },
          theme: {
            color: '#00f0ff'
          },
          modal: {
            ondismiss: function() {
              setIsUpdating(false);
              setMessage('Checkout cancelled');
            }
          }
        };

        const rzp = new window.Razorpay(options);
        rzp.on('payment.failed', function (response) {
          setIsUpdating(false);
          setMessage('ERROR: ' + (response.error.description || 'Payment failed'));
        });
        rzp.open();
      } else {
        setMessage(`ERROR: ${data.error || 'Failed to initialize subscription'}`);
        setIsUpdating(false);
      }
    } catch (err) {
      console.error('Purchase error:', err);
      setMessage('ERROR: Network failure during checkout');
      setIsUpdating(false);
    }
  };

  return (
    <div className="term-markdown-view">
      <motion.div 
        className="term-md-header"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="term-md-tag">[TIERS • COMPUTE CONFIGURATIONS]</div>
        <div className="term-md-title"># Subscription Models & Compute Nodes</div>
        <div className="term-md-subtitle">
          Choose your local compute allocation and model routing capability.
        </div>
      </motion.div>

      <div className="term-md-divider">================================================================================</div>

      {/* Promotional Notice */}
      <div className="term-md-card" style={{ marginBottom: '24px', borderColor: '#E5FF00', background: 'rgba(229, 255, 0, 0.02)' }}>
        <div style={{ color: '#E5FF00', fontWeight: 'bold', fontSize: '0.85rem', fontFamily: 'monospace', padding: '12px 16px', borderBottom: '1px solid rgba(229, 255, 0, 0.1)' }}>
          [PROMOTIONAL SYSTEM NOTICE • TEMPORARY ACCESS GRANTED]
        </div>
        <div style={{ padding: '14px 16px', color: '#ccc', fontSize: '0.85rem', lineHeight: '1.5', fontFamily: 'monospace' }}>
          All advanced tools (<strong>Image Generation</strong>, <strong>Blender Agent</strong>, <strong>Web Search Agent</strong>, <strong>Synthetic Eye</strong> for non-vision models, and <strong>Planning Agent</strong>) along with the global <strong>Experience Vector Database</strong> are currently <strong>FREE</strong> for all subscription tiers until June end (Extended through July end!).
        </div>
      </div>



      {message && (
        <div style={{ 
          background: message.startsWith('ERROR') ? 'rgba(231, 72, 86, 0.1)' : message.startsWith('SUCCESS') ? 'rgba(39, 201, 63, 0.1)' : 'rgba(255, 255, 255, 0.02)',
          border: message.startsWith('ERROR') ? '1px solid rgba(231, 72, 86, 0.3)' : message.startsWith('SUCCESS') ? '1px solid rgba(39, 201, 63, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)',
          color: message.startsWith('ERROR') ? '#e74856' : message.startsWith('SUCCESS') ? '#27c93f' : '#aaa',
          padding: '12px 16px',
          borderRadius: '8px',
          fontSize: '0.88rem',
          marginBottom: '20px',
          fontFamily: 'monospace'
        }}>
          {message}
        </div>
      )}

      <div className="term-md-section-title">## Available Node Tiers</div>

      <div className="term-md-highlights-list" style={{ marginBottom: '30px' }}>
        {tiers.map((t, i) => (
          <motion.div 
            key={t.name}
            className="term-md-card"
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.1 }}
          >
            <div className="term-md-card-border-top" style={{ color: '#222' }}>
              ┌── {t.num} / {t.name} ─────────────────────────────
            </div>
            <div className="term-md-card-content" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <strong className="term-md-highlight-title" style={{ color: t.color }}>{t.name}</strong>
                <span className="term-md-bullet" style={{ color: t.color }}>■</span>
              </div>
              {/* Price with referral discount if applicable */}
              {(() => {
                const disc = getDiscountedPrice(t);
                if (disc) return (
                  <div style={{ margin: '4px 0' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '1.1rem', color: '#555', fontFamily: 'monospace', textDecoration: 'line-through' }}>
                        {disc.orig}
                      </span>
                      <span style={{ fontSize: '1.25rem', color: '#00FF66', fontWeight: 'bold', fontFamily: 'monospace' }}>
                        {disc.discounted}
                      </span>
                    </div>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', marginTop: '5px', background: 'rgba(0,255,102,0.08)', border: '1px solid rgba(0,255,102,0.25)', borderRadius: '4px', padding: '2px 8px' }}>
                      <span style={{ color: '#00FF66', fontSize: '0.72rem', fontFamily: 'monospace', fontWeight: 'bold' }}>
                        ✓ {disc.pct >= 100 ? '100% OFF — REFERRAL REWARD' : `${disc.pct.toFixed(0)}% OFF — REFERRAL REWARD`}
                      </span>
                    </div>
                  </div>
                );
                return (
                  <div style={{ fontSize: '1.1rem', color: '#fff', fontWeight: 'bold', fontFamily: 'monospace', margin: '4px 0', wordBreak: 'break-all' }}>
                    {getDisplayPrice(t)}
                  </div>
                );
              })()}
              {billingPeriod === 'yearly' && t.id !== 'free' && (
                <div style={{ color: '#00FF66', fontSize: '0.75rem', fontFamily: 'monospace', marginBottom: '4px' }}>
                  {getSavingsText(t)}
                </div>
              )}
              <ul style={{ listStyle: 'none', padding: 0, margin: '8px 0 16px 0', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {t.features.map(f => {
                  const isCredits = f.toLowerCase().includes('credits');
                  return (
                    <li 
                      key={f} 
                      style={{ 
                        fontSize: '0.85rem', 
                        color: isCredits ? (t.color || '#00f0ff') : '#fff', 
                        fontWeight: isCredits ? 'bold' : 'normal',
                        display: 'flex', 
                        gap: '8px', 
                        alignItems: 'flex-start' 
                      }}
                    >
                      <span style={{ color: t.color }}>✓</span>
                      <span>{f}</span>
                    </li>
                  );
                })}
              </ul>
              <button 
                className="tw-pricing-btn" 
                style={{ borderColor: 'rgba(255,255,255,0.08)', color: '#fff' }}
                onClick={() => handleActivate(t)}
                disabled={isUpdating}
              >
                {isUpdating && activePlanId === t.id ? '> DEPLOYING...' : `> ACTIVATE ${t.name.toUpperCase()}`}
              </button>
            </div>
            <div className="term-md-card-border-bottom" style={{ color: '#222' }}>
              └─────────────────────────────────────────────────
            </div>
          </motion.div>
        ))}
      </div>

      {/* Credit Top-up Panel */}
      <CreditTopup />

      <div style={{ 
        color: '#444', 
        fontSize: '0.72rem', 
        textAlign: 'center', 
        marginTop: '16px', 
        borderTop: '1px solid rgba(255,255,255,0.04)', 
        paddingTop: '8px',
        fontFamily: 'monospace',
        lineHeight: '1.4'
      }}>
        [SYSTEM NOTE] Rollover quota & degradation mechanism: When a user buys 2 Pro plans and saves up quota, then degrades to a Hobby plan, they retain $7 in the active Hobby quota bank; the remaining $23 is converted to bonus credits at a 50% conversion rate.
      </div>
    </div>
  );
};

export const InlineAbout = () => {
  const team = [
    {
      initials: "SC",
      name: "Sarannya Chaudhuri",
      role: "Owner / Developer",
      tag: "Fullstack Mastery",
      color: "#00F0FF",
      desc: "The visionary architect behind UTIM. Specializing in both Frontend and Backend engineering, Sarannya ensures every line of code pushes the boundaries of autonomous development."
    },
    {
      initials: "AN",
      name: "Anushka Nath",
      role: "Co-owner / Marketing Lead",
      tag: "Strategic Growth",
      color: "#E5FF00",
      desc: "Leading the brand identity and growth strategy. Anushka translates complex AI capabilities into human stories, steering the marketing team towards global expansion."
    },
    {
      initials: "SR",
      name: "Swapnil Roy",
      role: "Video Editor",
      tag: "Cinematic Narrative",
      color: "#B266FF",
      desc: "Crafting the visual narrative of UTIM. Swapnil brings the agentic workflow to life through cinematic editing, ensuring our mission is seen as clearly as it is felt."
    },
    {
      initials: "SG",
      name: "Somesh Ganguly",
      role: "Marketing Assistant",
      tag: "Operational Excellence",
      color: "#00FF66",
      desc: "Supporting the marketing ecosystem. Somesh works behind the scenes to streamline operations and ensure our message reaches every developer who thinks, 'I want to make.'"
    }
  ];

  return (
    <div className="term-markdown-view">
      <motion.div 
        className="term-md-header"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="term-md-tag">[INITIATIVE • THE MANIFESTO]</div>
        <div className="term-md-title"># We are killing autocomplete.</div>
        <div className="term-md-subtitle">
          A collective of engineers, storytellers, and strategists dedicated to redefining how the world builds software.
        </div>
      </motion.div>

      <div className="term-md-divider">================================================================================</div>

      <div className="term-md-section-title">## Manifesto & Core Principles</div>
      
      <div className="term-md-highlights-list" style={{ marginBottom: '30px' }}>
        <motion.div className="term-md-card" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 }}>
          <div className="term-md-card-border-top">┌── 01 / The Problem ─────────────────────────────</div>
          <div className="term-md-card-content">
            <span className="term-md-bullet">■</span> <strong className="term-md-highlight-title" style={{ color: '#FF5555' }}>Context Switching & Boilerplate</strong>
            <p className="term-md-highlight-desc">Developers spend 40% of their time writing boilerplate and managing context across 15 different tabs. AI autocomplete tools only guess the next word. They do not understand the architecture. They do not understand the intention.</p>
          </div>
          <div className="term-md-card-border-bottom">└─────────────────────────────────────────────────</div>
        </motion.div>

        <motion.div className="term-md-card" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
          <div className="term-md-card-border-top">┌── 02 / The Solution ────────────────────────────</div>
          <div className="term-md-card-content">
            <span className="term-md-bullet">■</span> <strong className="term-md-highlight-title" style={{ color: '#00F0FF' }}>Autonomous Reasoning Engine</strong>
            <p className="term-md-highlight-desc">We built an autonomous reasoning engine. UTIM doesn't guess text; it operates a headless terminal. It reads the file system, generates checklists, writes files, compiles the application, reads errors, and fixes them autonomously.</p>
          </div>
          <div className="term-md-card-border-bottom">└─────────────────────────────────────────────────</div>
        </motion.div>

        <motion.div className="term-md-card" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 }}>
          <div className="term-md-card-border-top">┌── 03 / The Vision ──────────────────────────────</div>
          <div className="term-md-card-content">
            <span className="term-md-bullet">■</span> <strong className="term-md-highlight-title" style={{ color: '#E5FF00' }}>Systems Architecture Elevation</strong>
            <p className="term-md-highlight-desc">By removing the friction of syntax engineering, we elevate the developer from a "code typist" to a "systems architect". You provide the creative direction and logical constraints; UTIM handles the execution.</p>
          </div>
          <div className="term-md-card-border-bottom">└─────────────────────────────────────────────────</div>
        </motion.div>

        <motion.div className="term-md-card" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.4 }}>
          <div className="term-md-card-border-top">┌── 05 / Rich Terminal UI ────────────────────────</div>
          <div className="term-md-card-content">
            <span className="term-md-bullet">■</span> <strong className="term-md-highlight-title" style={{ color: '#B266FF' }}>Interactive TUI Engine</strong>
            <p className="term-md-highlight-desc">Built on Python Rich & prompt_toolkit, UTIM delivers split console panels, live execution spinners, tree inspectors, and keyboard-navigable command menus right in your terminal.</p>
          </div>
          <div className="term-md-card-border-bottom">└─────────────────────────────────────────────────</div>
        </motion.div>

        <motion.div className="term-md-card" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.5 }}>
          <div className="term-md-card-border-top">┌── 06 / Self-Healing Visual QA ──────────────────</div>
          <div className="term-md-card-content">
            <span className="term-md-bullet">■</span> <strong className="term-md-highlight-title" style={{ color: '#00FF66' }}>Playwright Browser Loop</strong>
            <p className="term-md-highlight-desc">Launches headless Playwright browser instances during builds, captures visual screenshots, detects CSS conflicts, and self-heals layout bugs before deployment.</p>
          </div>
          <div className="term-md-card-border-bottom">└─────────────────────────────────────────────────</div>
        </motion.div>

        <motion.div className="term-md-card" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.6 }}>
          <div className="term-md-card-border-top">┌── 07 / Zero-Pollution Rollbacks & MCP ──────────</div>
          <div className="term-md-card-content">
            <span className="term-md-bullet">■</span> <strong className="term-md-highlight-title" style={{ color: '#FF8C00' }}>Transaction Revert Stack & Tooling</strong>
            <p className="term-md-highlight-desc">Logs every package install and code modification in a local transaction database. Run /undo or /rewind to instantly revert files to any turn, while leveraging standard Model Context Protocol (MCP) servers for PostgreSQL, Figma, and GitHub integrations.</p>
          </div>
          <div className="term-md-card-border-bottom">└─────────────────────────────────────────────────</div>
        </motion.div>

        <motion.div className="term-md-card" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.7 }} style={{ gridColumn: '1 / -1' }}>
          <div className="term-md-card-border-top">┌── 08 / Neural Pattern Recognition Engine ────────</div>
          <div className="term-md-card-content">
            <span className="term-md-bullet">■</span> <strong className="term-md-highlight-title" style={{ color: '#00F0FF' }}>Human-like Cognitive Adaptation</strong>
            <p className="term-md-highlight-desc">Unlike basic AI tools that rely on word matching, UTIM abstracts execution failures into neural conceptual patterns via Hugging Face embeddings. It dynamically recognizes situations (like command syntax or operator errors) and adapts automatically on future executions.</p>
          </div>
          <div className="term-md-card-border-bottom">└─────────────────────────────────────────────────</div>
        </motion.div>
      </div>

      <div className="term-md-section-title">## 04 / The Architects (The Minds Behind UTIM)</div>
      
      <div className="term-md-highlights-list">
        {team.map((member, i) => (
          <motion.div 
            key={member.name} 
            className="term-md-card"
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.4 + i * 0.08, duration: 0.2 }}
          >
            <div className="term-md-card-border-top">┌── {member.initials} • {member.tag} ─────────────────────────────</div>
            <div className="term-md-card-content">
              <span className="term-md-bullet">■</span> <strong className="term-md-highlight-title" style={{ color: member.color }}>{member.name}</strong> <span style={{ color: '#aaa', fontSize: '0.85rem' }}>({member.role})</span>
              <p className="term-md-highlight-desc">{member.desc}</p>
            </div>
            <div className="term-md-card-border-bottom">└─────────────────────────────────────────────────</div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export const InlineConnect = () => {
  const platforms = [
    { name: 'X / Twitter', handle: '@UTIM_AI', tag: 'Announcements', desc: 'Follow for real-time model updates, benchmark releases, and developer news.', link: 'https://x.com/UTIM_AI', color: '#1DA1F2' },
    { name: 'Instagram', handle: '@utim__ai', tag: 'Visual Feed', desc: 'Behind the scenes, UI mockups, agent demos, and release highlights.', link: 'https://www.instagram.com/utim__ai/', color: '#E4405F' },
    { name: 'Reddit', handle: 'r/UTIM_AI', tag: 'Community Hub', desc: 'Join discussions, share CLI tools, showcase builds, and get help.', link: 'https://www.reddit.com/r/UTIM_AI/', color: '#FF4500' },
    { name: 'LinkedIn', handle: 'UTIM AI', tag: 'Company & Network', desc: 'Connect with our engineering team, career updates, and enterprise partnerships.', link: 'https://www.linkedin.com/company/utim-ai/', color: '#0A66C2' },
    { name: 'Discord Community', handle: 'UTIM Server', tag: 'Developer Guild', desc: 'Join our server to share agent workflows, prompts, and chat with creators.', link: 'https://discord.com/invite/wGB7M8pMEy', color: '#5865F2' },
    { name: 'Direct Email Support', handle: 'support@utim.dev', tag: 'Enterprise Hub', desc: 'Contact uthinkimake.official@gmail.com for enterprise inquiries and support.', link: 'mailto:uthinkimake.official@gmail.com', color: '#EA4335' }
  ];
  return (
    <div className="term-markdown-view">
      <motion.div 
        className="term-md-header"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="term-md-tag">[SECURE NETWORK MATRIX]</div>
        <div className="term-md-title"># Connect with UTIM Core</div>
        <div className="term-md-subtitle">
          Establish an encrypted high-speed link with our engineering ecosystem and social network channels.
        </div>
      </motion.div>

      <div className="term-md-divider">================================================================================</div>

      <div className="term-md-section-title">## Communication Nodes</div>
      <div className="term-md-highlights-list">
        {platforms.map((p, i) => (
          <motion.a 
            key={p.name}
            href={p.link}
            target={p.link.startsWith('mailto:') ? '_self' : '_blank'}
            rel="noreferrer"
            className="term-md-card"
            style={{ textDecoration: 'none' }}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.05, duration: 0.2 }}
          >
            <div className="term-md-card-border-top">┌── {p.tag} • {p.handle} ──────────────────────────────────────</div>
            <div className="term-md-card-content">
              <span className="term-md-bullet">■</span> <strong className="term-md-highlight-title" style={{ color: p.color }}>{p.name}</strong>
              <p className="term-md-highlight-desc">{p.desc}</p>
            </div>
            <div className="term-md-card-border-bottom">└─────────────────────────────────────────────────</div>
          </motion.a>
        ))}
      </div>
    </div>
  );
};

const MODELS_DATA = {
  free: [
    { id: 'nex-agi/nex-n2-pro:free', input: 0.0002, output: 0.0003, context: '262,144', caps: ['code', 'chat', 'tool_use'] },
    { id: 'poolside/laguna-m.1:free', input: 0.0002, output: 0.0003, context: '262,144', caps: ['code', 'chat', 'tool_use'] },
    { id: 'cohere/north-mini-code:free', input: 0.0002, output: 0.0003, context: '128,000', caps: ['code', 'chat', 'tool_use'] },
    { id: 'openrouter/free', input: 0.0002, output: 0.0003, context: '200,000', caps: ['chat'] },
    { id: 'google/gemma-4-31b-it:free', input: 0.0002, output: 0.0003, context: '262,144', caps: ['chat'] },
    { id: 'google/gemma-4-26b-a4b-it:free', input: 0.0002, output: 0.0003, context: '262,144', caps: ['chat'] },
    { id: 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free', input: 0.0002, output: 0.0003, context: '128,000', caps: ['chat'] },
    { id: 'nvidia/nemotron-nano-12b-v2-vl:free', input: 0.0002, output: 0.0003, context: '128,000', caps: ['chat'] },
    { id: 'openai/gpt-oss-20b:free', input: 0.0002, output: 0.0003, context: '131,072', caps: ['chat'] },
    { id: 'poolside/laguna-xs.2:free', input: 0.0002, output: 0.0003, context: '32,000', caps: ['chat'] },
    { id: 'poolside/laguna-s-2.1:free', input: 0.0002, output: 0.0003, context: '262,144', caps: ['code', 'chat', 'tool_use'] },
    { id: 'qwen/qwen3-next-80b-a3b-instruct:free', input: 0.0002, output: 0.0003, context: '262,144', caps: ['chat'] }
  ],
  premium: [
    { id: 'inclusionai/ling-2.6-flash', input: 0.0105, output: 0.0315, context: '262,144', caps: ['chat', 'code'] },
    { id: 'google/gemini-3.6-flash', input: 1.5750, output: 7.8750, context: '1,048,576', caps: ['chat', 'code'] },
    { id: 'deepseek/deepseek-v4-flash', input: 0.1029, output: 0.2058, context: '1,048,576', caps: ['chat', 'code'] },
    { id: 'aion-labs/aion-3.0-mini', input: 0.7350, output: 1.4700, context: '131,072', caps: ['chat', 'code'] },
    { id: 'minimax/minimax-m2.5', input: 0.1575, output: 0.9450, context: '204,800', caps: ['chat', 'code'] },
    { id: 'xiaomi/mimo-v2.5', input: 0.1470, output: 0.2940, context: '1,048,576', caps: ['chat'] },
    { id: 'stepfun/step-3.7-flash', input: 0.2100, output: 1.2075, context: '256,000', caps: ['chat'] },
    { id: 'inclusionai/ling-2.6-1t', input: 0.0788, output: 0.6562, context: '262,144', caps: ['chat'] },
    { id: 'kwaipilot/kat-coder-pro-v2', input: 0.3150, output: 1.2600, context: '256,000', caps: ['chat', 'code'] },
    { id: 'minimax/minimax-m3', input: 0.3150, output: 1.2600, context: '1,048,576', caps: ['chat'] },
    { id: 'qwen/qwen3.7-plus', input: 0.3360, output: 1.3440, context: '1,000,000', caps: ['chat', 'code'] },
    { id: 'qwen/qwen3.6-plus', input: 0.3413, output: 2.0475, context: '1,000,000', caps: ['chat', 'code'] },
    { id: 'moonshotai/kimi-k2.5', input: 0.5985, output: 2.9925, context: '262,144', caps: ['chat', 'code'] },
    { id: 'z-ai/glm-4.7', input: 0.4200, output: 1.8375, context: '202,752', caps: ['chat', 'code'] },
    { id: 'deepseek/deepseek-v4-pro', input: 0.4567, output: 0.9135, context: '1,048,576', caps: ['chat', 'code'] },
    { id: 'z-ai/glm-5', input: 0.9975, output: 3.3075, context: '202,752', caps: ['chat', 'code'] },
    { id: 'deepseek/deepseek-r1', input: 0.7350, output: 2.6250, context: '163,840', caps: ['chat', 'code'] },
    { id: 'openai/gpt-5.4-mini', input: 0.7875, output: 4.7250, context: '400,000', caps: ['chat', 'code'] },
    { id: 'z-ai/glm-5.2', input: 1.0055, output: 3.1601, context: '1,048,576', caps: ['chat', 'code'] },
    { id: 'moonshotai/kimi-k2.6', input: 0.9975, output: 4.2000, context: '262,144', caps: ['chat'] },
    { id: 'moonshotai/kimi-k2.7-code', input: 0.7875, output: 3.6750, context: '262,144', caps: ['chat', 'code'] },
    { id: 'xiaomi/mimo-v2-pro', input: 1.0000, output: 2.0000, context: '1,048,576', caps: ['chat'] },
    { id: 'aion-labs/aion-3.0', input: 3.1500, output: 6.3000, context: '131,072', caps: ['chat', 'code'] },
    { id: 'minimax/minimax-m2.7', input: 0.2625, output: 1.0500, context: '204,800', caps: ['chat'] },
    { id: 'z-ai/glm-5.1', input: 1.0143, output: 3.1878, context: '202,752', caps: ['chat'] },
    { id: 'xiaomi/mimo-v2.5-pro', input: 0.4567, output: 0.9135, context: '1,048,576', caps: ['chat'] },
    { id: 'nex-agi/nex-n2-pro', input: 0.2625, output: 1.0500, context: '262,144', caps: ['chat', 'code'] },
    { id: 'x-ai/grok-build-0.1', input: 1.0500, output: 2.1000, context: '256,000', caps: ['chat', 'code'] },
    { id: 'z-ai/glm-5-turbo', input: 1.2600, output: 4.2000, context: '202,752', caps: ['chat', 'code'] },
    { id: 'google/gemini-3.1-pro-preview', input: 2.1000, output: 12.6000, context: '1,048,576', caps: ['chat'] },
    { id: 'google/gemini-3.1-pro-preview-customtools', input: 2.1000, output: 12.6000, context: '1,048,756', caps: ['chat', 'code'] },
    { id: 'x-ai/grok-4.3', input: 1.3125, output: 2.6250, context: '1,000,000', caps: ['chat'] },
    { id: 'qwen/qwen3.7-max', input: 1.5488, output: 4.6463, context: '1,000,000', caps: ['chat', 'code'] },
    { id: 'x-ai/grok-4.20', input: 1.3125, output: 2.6250, context: '2,000,000', caps: ['chat', 'code'] },
    { id: 'openai/gpt-5.6-sol', input: 5.2500, output: 31.5000, context: '1,050,000', caps: ['chat', 'code'] },
    { id: 'google/gemini-3.5-flash', input: 1.5750, output: 9.4500, context: '1,048,576', caps: ['chat'] },
    { id: 'x-ai/grok-4.5', input: 2.1000, output: 6.3000, context: '500,000', caps: ['chat', 'code'] },
    { id: 'openai/gpt-5.6-terra', input: 2.6250, output: 15.7500, context: '1,050,000', caps: ['chat', 'code'] },
    { id: 'anthropic/claude-sonnet-5', input: 2.1000, output: 10.5000, context: '1,000,000', caps: ['chat', 'code'] },
    { id: 'openai/gpt-5.6-luna', input: 1.0500, output: 6.3000, context: '1,050,000', caps: ['chat', 'code'] },
    { id: 'openai/gpt-5.4', input: 2.6250, output: 15.7500, context: '1,050,000', caps: ['chat'] },
    { id: 'anthropic/claude-sonnet-4.6', input: 3.1500, output: 15.7500, context: '1,000,000', caps: ['chat'] },
    { id: 'openai/gpt-5.6-sol-pro', input: 5.2500, output: 31.5000, context: '1,050,000', caps: ['chat', 'code'] },
    { id: 'anthropic/claude-sonnet-4.5', input: 3.1500, output: 15.7500, context: '1,000,000', caps: ['chat', 'code'] },
    { id: 'openai/gpt-5.6-terra-pro', input: 2.6250, output: 15.7500, context: '1,050,000', caps: ['chat', 'code'] },
    { id: 'openai/gpt-5.6-luna-pro', input: 1.0500, output: 6.3000, context: '1,050,000', caps: ['chat', 'code'] },
    { id: 'openai/gpt-5.5', input: 5.2500, output: 31.5000, context: '1,050,000', caps: ['chat', 'code'] },
    { id: 'anthropic/claude-opus-4.5', input: 5.2500, output: 26.2500, context: '200,000', caps: ['chat', 'code'] },
    { id: 'anthropic/claude-opus-4.7', input: 5.2500, output: 26.2500, context: '1,000,000', caps: ['chat', 'code'] },
    { id: 'anthropic/claude-opus-4.8', input: 5.2500, output: 26.2500, context: '1,000,000', caps: ['chat', 'code'] },
    { id: 'openai/gpt-5.3-codex', input: 1.8375, output: 14.7000, context: '400,000', caps: ['chat'] },
    { id: 'anthropic/claude-fable-5', input: 10.5000, output: 52.5000, context: '1,000,000', caps: ['chat'] },
    { id: 'anthropic/claude-opus-4.6', input: 5.2500, output: 26.2500, context: '1,000,000', caps: ['chat'] },
    { id: 'kwaipilot/kat-coder-air-v2.5', input: 0.1575, output: 0.6300, context: '256,000', caps: ['code', 'chat', 'tool_use'] },
    { id: 'kwaipilot/kat-coder-pro-v2.5', input: 0.7770, output: 3.1080, context: '256,000', caps: ['code', 'chat', 'tool_use'] },
    { id: 'nex-agi/nex-n2-mini', input: 0.0263, output: 0.1050, context: '262,144', caps: ['code', 'chat', 'tool_use'] },
    { id: 'thinkingmachines/inkling', input: 0.00105, output: 0.00425, context: '1,048,576', caps: ['chat', 'code'] },
    { id: 'moonshotai/kimi-k3', input: 0.00315, output: 0.01575, context: '1,000,000', caps: ['chat', 'reasoning'] },
    { id: 'meta/muse-spark-1.1', input: 0.00131, output: 0.00446, context: '1,048,576', caps: ['chat', 'code', 'multimodal'] }
  ],
  image: [
    { id: 'krea/krea-2-medium-turbo', input: 0.0000, output: 0.01575, context: '100,000', caps: ['image_generation'] },
    { id: 'krea/krea-2-medium', input: 0.0000, output: 0.0315, context: '100,000', caps: ['image_generation'] },
    { id: 'krea/krea-2-large', input: 0.0000, output: 0.0630, context: '100,000', caps: ['image_generation'] },
    { id: 'black-forest-labs/flux.2-flex', input: 0.0000, output: 0.0306, context: '100,000', caps: ['image_generation'] },
    { id: 'black-forest-labs/flux.2-max', input: 0.0000, output: 0.0510, context: '100,000', caps: ['image_generation'] },
    { id: 'black-forest-labs/flux.2-klein-4b', input: 0.0000, output: 0.0102, context: '100,000', caps: ['image_generation'] },
    { id: 'sourceful/riverflow-v2-fast', input: 0.0000, output: 0.0102, context: '100,000', caps: ['image_generation'] },
    { id: 'sourceful/riverflow-v2-pro', input: 0.0000, output: 0.0357, context: '100,000', caps: ['image_generation'] },
    { id: 'sourceful/riverflow-v2.5-fast', input: 0.0000, output: 0.0102, context: '100,000', caps: ['image_generation'] },
    { id: 'google/gemini-3-pro-image-preview', input: 0.0000, output: 12.6000, context: '65,536', caps: ['image_generation'] },
    { id: 'google/gemini-3.1-flash-image-preview', input: 0.0000, output: 3.1500, context: '131,072', caps: ['chat', 'image'] },
    { id: 'google/gemini-3.1-flash-image', input: 0.0000, output: 3.1500, context: '131,072', caps: ['image_generation'] },
    { id: 'openai/gpt-5-image-mini', input: 0.0000, output: 2.1000, context: '400,000', caps: ['image_generation'] },
    { id: 'openai/gpt-image-2', input: 0.0204, output: 0.0204, context: '100,000', caps: ['image_generation'] },
    { id: 'recraft/recraft-v4.1', input: 0.0000, output: 0.0357, context: '100,000', caps: ['image_generation'] },
    { id: 'recraft/recraft-v4.1-pro', input: 0.0000, output: 0.2142, context: '100,000', caps: ['image_generation'] },
    { id: 'recraft/recraft-v4.1-utility', input: 0.0000, output: 0.0357, context: '100,000', caps: ['image_generation'] },
    { id: 'recraft/recraft-v4.1-utility-pro', input: 0.0000, output: 0.3060, context: '100,000', caps: ['image_generation'] },
    { id: 'recraft/recraft-v4.1-vector', input: 0.0000, output: 0.0816, context: '100,000', caps: ['image_generation'] },
    { id: 'recraft/recraft-v4.1-pro-vector', input: 0.0000, output: 0.3060, context: '100,000', caps: ['image_generation'] },
    { id: 'x-ai/grok-imagine-image-quality', input: 0.0000, output: 0.0408, context: '100,000', caps: ['image_generation'] },
    { id: 'microsoft/mai-image-2.5', input: 0.0000, output: 0.0204, context: '100,000', caps: ['image_generation'] },
    { id: 'sourceful/riverflow-v2.5-pro', input: 0.0000, output: 0.0408, context: '100,000', caps: ['image_generation'] },
    { id: 'black-forest-labs/flux.2-pro', input: 0.0000, output: 0.0306, context: '100,000', caps: ['image_generation'] },
    { id: 'bytedance-seed/seedream-4.5', input: 0.0000, output: 0.0408, context: '100,000', caps: ['image_generation'] },
    { id: 'recraft/recraft-v3', input: 0.0000, output: 0.0408, context: '100,000', caps: ['image_generation'] },
    { id: 'recraft/recraft-v4', input: 0.0000, output: 0.0408, context: '100,000', caps: ['image_generation'] },
    { id: 'recraft/recraft-v4-pro', input: 0.0000, output: 0.2550, context: '100,000', caps: ['image_generation'] },
    { id: 'recraft/recraft-v4-vector', input: 0.0000, output: 0.0816, context: '100,000', caps: ['image_generation'] },
    { id: 'recraft/recraft-v4-pro-vector', input: 0.0000, output: 0.3060, context: '100,000', caps: ['image_generation'] },
    { id: 'google/gemini-3-pro-image', input: 0.0000, output: 12.6000, context: '65,536', caps: ['image_generation'] },
    { id: 'openai/gpt-image-1', input: 0.0020, output: 0.0020, context: '100,000', caps: ['image_generation'] },
    { id: 'openai/gpt-image-1-mini', input: 0.0005, output: 0.0005, context: '100,000', caps: ['image_generation'] },
    { id: 'google/gemini-2.5-flash-image', input: 0.0000, output: 2.6250, context: '32,768', caps: ['image_generation'] },
    { id: 'openai/gpt-5-image', input: 0.0000, output: 10.5000, context: '400,000', caps: ['image_generation'] }
  ]
};

const ModelsPricingDoc = () => {
  const [search, setSearch] = useState('');
  const [tab, setTab] = useState('all');

  const filterModels = (list) => {
    return list.filter(m => {
      const matchSearch = m.id.toLowerCase().includes(search.toLowerCase()) || 
                          m.caps.some(c => c.toLowerCase().includes(search.toLowerCase()));
      return matchSearch;
    });
  };

  const categories = [
    { key: 'all', label: 'All Models' },
    { key: 'free', label: 'Free / Standard' },
    { key: 'premium', label: 'Premium Text & Code' },
    { key: 'image', label: 'Image Gen' },
  ];

  const renderTable = (models) => {
    if (models.length === 0) {
      return <div style={{ color: '#555', fontStyle: 'italic', padding: '8px' }}>No models match search filters.</div>;
    }
    return (
      <div style={{ overflowX: 'auto', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '4px', background: 'rgba(0,0,0,0.2)' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.72rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.02)' }}>
              <th style={{ padding: '8px 10px', color: '#888', fontWeight: 'bold' }}>Model ID</th>
              <th style={{ padding: '8px 10px', color: '#888', fontWeight: 'bold', width: '90px' }}>Input/1K</th>
              <th style={{ padding: '8px 10px', color: '#888', fontWeight: 'bold', width: '90px' }}>Output/1K</th>
              <th style={{ padding: '8px 10px', color: '#888', fontWeight: 'bold', width: '90px' }}>Context</th>
              <th style={{ padding: '8px 10px', color: '#888', fontWeight: 'bold' }}>Capabilities</th>
            </tr>
          </thead>
          <tbody>
            {models.map((m, idx) => (
              <tr 
                key={m.id} 
                style={{ 
                  borderBottom: '1px solid rgba(255,255,255,0.03)',
                  background: idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)'
                }}
              >
                <td style={{ padding: '8px 10px', fontFamily: 'monospace', color: '#00F0FF' }}>{m.id}</td>
                <td style={{ padding: '8px 10px', color: '#ccc' }}>{m.input.toFixed(4)}</td>
                <td style={{ padding: '8px 10px', color: '#ccc' }}>{m.output.toFixed(4)}</td>
                <td style={{ padding: '8px 10px', color: '#aaa' }}>{m.context}</td>
                <td style={{ padding: '8px 10px', display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                  {m.caps.map(cap => {
                    let color = '#888';
                    let bg = 'rgba(255,255,255,0.05)';
                    if (cap === 'code') { color = '#E5FF00'; bg = 'rgba(229,255,0,0.1)'; }
                    else if (cap === 'chat') { color = '#00F0FF'; bg = 'rgba(0,240,255,0.1)'; }
                    else if (cap === 'image_generation' || cap === 'image') { color = '#FF66B2'; bg = 'rgba(255,102,178,0.1)'; }
                    else if (cap === 'tool_use') { color = '#00FF66'; bg = 'rgba(0,255,102,0.1)'; }
                    return (
                      <span 
                        key={cap} 
                        style={{ 
                          color, 
                          background: bg,
                          padding: '1px 5px', 
                          borderRadius: '3px', 
                          fontSize: '0.62rem',
                          border: `1px solid ${color}33`
                        }}
                      >
                        {cap}
                      </span>
                    );
                  })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div style={{ color: '#fff', fontFamily: 'monospace', fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div>
        <h1 style={{ color: '#00F0FF', fontSize: '1.25rem', margin: '0 0 4px 0', borderBottom: '1px solid rgba(0,240,255,0.2)', paddingBottom: '6px' }}># Supported Models & Pricing</h1>
        <p style={{ color: '#aaa', fontSize: '0.75rem', lineHeight: '1.4', margin: '6px 0 0 0' }}>
          UTIM CLI dynamically fetches the latest pricing from OpenRouter daily. Prices show <strong>credits per 1,000 tokens</strong> ($1 USD = 1,000 credits) and include a <strong>5% platform markup fee</strong> (free models are excluded).
        </p>
      </div>

      <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
        <input 
          type="text" 
          placeholder="Filter by ID or capability..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '4px',
            color: '#fff',
            padding: '6px 10px',
            fontSize: '0.75rem',
            fontFamily: 'monospace',
            outline: 'none',
            flex: '1',
            minWidth: '200px'
          }}
        />

        <div style={{ display: 'flex', gap: '4px' }}>
          {categories.map(cat => (
            <button
              key={cat.key}
              onClick={() => setTab(cat.key)}
              style={{
                background: tab === cat.key ? '#00F0FF' : 'rgba(255,255,255,0.03)',
                color: tab === cat.key ? '#000' : '#888',
                border: tab === cat.key ? 'none' : '1px solid rgba(255,255,255,0.05)',
                borderRadius: '4px',
                padding: '4px 8px',
                fontSize: '0.7rem',
                fontWeight: 'bold',
                cursor: 'pointer',
                transition: 'all 0.15s'
              }}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {(tab === 'all' || tab === 'free') && (
          <div>
            <h3 style={{ color: '#00FF66', fontSize: '0.85rem', margin: '0 0 8px 0' }}>■ Free / Standard Tiers</h3>
            {renderTable(filterModels(MODELS_DATA.free))}
          </div>
        )}

        {(tab === 'all' || tab === 'premium') && (
          <div>
            <h3 style={{ color: '#FFA500', fontSize: '0.85rem', margin: '0 0 8px 0' }}>■ Premium Text & Code Tiers</h3>
            {renderTable(filterModels(MODELS_DATA.premium))}
          </div>
        )}

        {(tab === 'all' || tab === 'image') && (
          <div>
            <h3 style={{ color: '#FF66B2', fontSize: '0.85rem', margin: '0 0 8px 0' }}>■ Image Generation Tiers</h3>
            {renderTable(filterModels(MODELS_DATA.image))}
          </div>
        )}
      </div>
    </div>
  );
};

const DOCS_TREE = [
  {
    category: 'GETTING STARTED',
    items: [
      { id: 'overview', title: 'Complete Manual' },
      { id: 'quickstart', title: 'Quickstart' },
      { id: 'business-readiness', title: 'Business Readiness' },
      { id: 'models-pricing', title: 'Models & Pricing' },
      { id: 'changelog', title: 'Changelog' },
    ]
  },
  {
    category: 'CORE CONCEPTS',
    items: [
      { id: 'how-it-works', title: 'How UTIM Works' },
      { id: 'extend-code', title: 'Extend UTIM (MCP)' },
      { id: 'utim-dir', title: 'Explore the .utim_tmp Directory' },
      { id: 'context-window', title: 'Explore the Context Window' },
      { id: 'prompt-caching', title: 'Prompt Caching' },
    ]
  },
  {
    category: 'USE UTIM CLI',
    items: [
      { id: 'instructions', title: 'Store Instructions & Memories' },
      { id: 'permission-modes', title: 'Permission Modes' },
      { id: 'manage-sessions', title: 'Manage Sessions' },
      { id: 'workflows', title: 'Common Workflows' },
    ]
  },
  {
    category: 'PLATFORMS & INTEGRATIONS',
    items: [
      { id: 'integrations-overview', title: 'Overview' },
      { id: 'web-desktop', title: 'Web & Desktop Apps' },
      { id: 'ci-cd', title: 'Code Review & CI/CD' },
    ]
  },
  {
    category: 'POLICIES',
    items: [
      { id: 'privacy', title: 'Privacy Policy' },
      { id: 'terms', title: 'Terms of Service' },
      { id: 'refund', title: 'Refund Policy' },
      { id: 'license', title: 'Proprietary License' },
    ]
  }
];

const DOCS_ARTICLES = {
  'overview': {
    title: 'Complete Manual',
    content: docsMd
  },
  'business-readiness': {
    title: 'Business Readiness',
    content: `
# Business Readiness

UTIM is suitable for technical beta users and early adopters today. To position it as fully business-ready for paid production customers, the remaining work is mostly operational: documentation consistency, security policy, release automation, support commitments, and billing verification.

### Ready signals

- Real CLI package and \`utim\` entrypoint.
- Interactive terminal UI and single-task mode.
- Login, logout, quota, billing, plans, usage, and upgrade flows.
- Diagnostics through \`utim doctor\` and \`/doctor\`.
- Local rollback through \`/undo\`, \`/redo\`, and \`/rewind\`.
- Redacted support bundle generation through \`/report\`.
- MCP integration and tool toggles.
- Website pages for docs, pricing, support, terms, privacy, refund, and license.

### Gaps before enterprise positioning

- Synchronize README, website docs, package version, CLI about text, and visible website version.
- Add automated release gates for landing-site build, Python tests, package smoke tests, and docs rendering.
- Publish a security policy and vulnerability reporting process.
- Document exactly what remains local and what is sent to UTIM services or model providers.
- Add clear support SLAs that match paid plan marketing.
- Add compatibility matrix for Windows, macOS, Linux, shells, Python, Node, and optional dependencies.
- Verify npm-wrapper installation and Python-source installation in clean environments.
- Add end-to-end tests for login, checkout, quota, docs, and support chat docs retrieval.

### Verdict

Business-ready for beta and early paid validation. Not yet fully enterprise-ready until the operational and trust-documentation gaps above are closed.
    `
  },
  'models-pricing': {
    title: 'Models & Pricing',
    content: `
# Supported Models & Pricing

UTIM CLI supports a diverse registry of LLM and image generation models. All prices listed below represent **credits per 1,000 tokens** (1 USD = 1,000 credits) and include the dynamic **5% platform markup fee** over base OpenRouter rates (excluding free models).

### A. Free / Standard Models
| Model ID | Input Cost (credits/1K) | Output Cost (credits/1K) | Context Window | Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| \`nex-agi/nex-n2-pro:free\` | 0.0002 | 0.0003 | 262,144 | code, chat, tool_use  |
| \`poolside/laguna-m.1:free\` | 0.0002 | 0.0003 | 262,144 | code, chat, tool_use  |
| \`cohere/north-mini-code:free\` | 0.0002 | 0.0003 | 128,000 | code, chat, tool_use  |
| \`openrouter/free\` | 0.0002 | 0.0003 | 200,000 | chat  |
| \`google/gemma-4-31b-it:free\` | 0.0002 | 0.0003 | 262,144 | chat  |
| \`google/gemma-4-26b-a4b-it:free\` | 0.0002 | 0.0003 | 262,144 | chat  |
| \`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free\` | 0.0002 | 0.0003 | 128,000 | chat  |
| \`nvidia/nemotron-nano-12b-v2-vl:free\` | 0.0002 | 0.0003 | 128,000 | chat  |
| \`openai/gpt-oss-20b:free\` | 0.0002 | 0.0003 | 131,072 | chat  |
| \`poolside/laguna-xs.2:free\` | 0.0002 | 0.0003 | 32,000 | chat  |
| \`poolside/laguna-s-2.1:free\` | 0.0002 | 0.0003 | 262,144 | code, chat, tool_use  |
| \`qwen/qwen3-next-80b-a3b-instruct:free\` | 0.0002 | 0.0003 | 262,144 | chat  |

### B. Premium Text & Code Models
| Model ID | Input Cost (credits/1K) | Output Cost (credits/1K) | Context Window | Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| \`inclusionai/ling-2.6-flash\` | 0.0105 | 0.0315 | 262,144 | chat, code  |
| \`google/gemini-3.6-flash\` | 1.5750 | 7.8750 | 1,048,576 | chat, code  |
| \`deepseek/deepseek-v4-flash\` | 0.1029 | 0.2058 | 1,048,576 | chat, code  |
| \`aion-labs/aion-3.0-mini\` | 0.7350 | 1.4700 | 131,072 | chat, code  |
| \`minimax/minimax-m2.5\` | 0.1575 | 0.9450 | 204,800 | chat, code  |
| \`xiaomi/mimo-v2.5\` | 0.1470 | 0.2940 | 1,048,576 | chat  |
| \`stepfun/step-3.7-flash\` | 0.2100 | 1.2075 | 256,000 | chat  |
| \`inclusionai/ling-2.6-1t\` | 0.0788 | 0.6562 | 262,144 | chat  |
| \`kwaipilot/kat-coder-pro-v2\` | 0.3150 | 1.2600 | 256,000 | chat, code  |
| \`minimax/minimax-m3\` | 0.3150 | 1.2600 | 1,048,576 | chat  |
| \`qwen/qwen3.7-plus\` | 0.3360 | 1.3440 | 1,000,000 | chat, code  |
| \`qwen/qwen3.6-plus\` | 0.3413 | 2.0475 | 1,000,000 | chat, code  |
| \`moonshotai/kimi-k2.5\` | 0.5985 | 2.9925 | 262,144 | chat, code  |
| \`z-ai/glm-4.7\` | 0.4200 | 1.8375 | 202,752 | chat, code  |
| \`deepseek/deepseek-v4-pro\` | 0.4567 | 0.9135 | 1,048,576 | chat, code  |
| \`z-ai/glm-5\` | 0.9975 | 3.3075 | 202,752 | chat, code  |
| \`deepseek/deepseek-r1\` | 0.7350 | 2.6250 | 163,840 | chat, code  |
| \`openai/gpt-5.4-mini\` | 0.7875 | 4.7250 | 400,000 | chat, code  |
| \`z-ai/glm-5.2\` | 1.0055 | 3.1601 | 1,048,576 | chat, code  |
| \`moonshotai/kimi-k2.6\` | 0.9975 | 4.2000 | 262,144 | chat  |
| \`moonshotai/kimi-k2.7-code\` | 0.7875 | 3.6750 | 262,144 | chat, code  |
| \`xiaomi/mimo-v2-pro\` | 1.0000 | 2.0000 | 1,048,576 | chat  |
| \`aion-labs/aion-3.0\` | 3.1500 | 6.3000 | 131,072 | chat, code  |
| \`minimax/minimax-m2.7\` | 0.2625 | 1.0500 | 204,800 | chat  |
| \`z-ai/glm-5.1\` | 1.0143 | 3.1878 | 202,752 | chat  |
| \`xiaomi/mimo-v2.5-pro\` | 0.4567 | 0.9135 | 1,048,576 | chat  |
| \`nex-agi/nex-n2-pro\` | 0.2625 | 1.0500 | 262,144 | chat, code  |
| \`x-ai/grok-build-0.1\` | 1.0500 | 2.1000 | 256,000 | chat, code  |
| \`z-ai/glm-5-turbo\` | 1.2600 | 4.2000 | 202,752 | chat, code  |
| \`google/gemini-3.1-pro-preview\` | 2.1000 | 12.6000 | 1,048,576 | chat  |
| \`google/gemini-3.1-pro-preview-customtools\` | 2.1000 | 12.6000 | 1,048,756 | chat, code  |
| \`x-ai/grok-4.3\` | 1.3125 | 2.6250 | 1,000,000 | chat  |
| \`qwen/qwen3.7-max\` | 1.5488 | 4.6463 | 1,000,000 | chat, code  |
| \`x-ai/grok-4.20\` | 1.3125 | 2.6250 | 2,000,000 | chat, code  |
| \`openai/gpt-5.6-sol\` | 5.2500 | 31.5000 | 1,050,000 | chat, code  |
| \`google/gemini-3.5-flash\` | 1.5750 | 9.4500 | 1,048,576 | chat  |
| \`x-ai/grok-4.5\` | 2.1000 | 6.3000 | 500,000 | chat, code  |
| \`openai/gpt-5.6-terra\` | 2.6250 | 15.7500 | 1,050,000 | chat, code  |
| \`anthropic/claude-sonnet-5\` | 2.1000 | 10.5000 | 1,000,000 | chat, code  |
| \`openai/gpt-5.6-luna\` | 1.0500 | 6.3000 | 1,050,000 | chat, code  |
| \`openai/gpt-5.4\` | 2.6250 | 15.7500 | 1,050,000 | chat  |
| \`anthropic/claude-sonnet-4.6\` | 3.1500 | 15.7500 | 1,000,000 | chat  |
| \`openai/gpt-5.6-sol-pro\` | 5.2500 | 31.5000 | 1,050,000 | chat, code  |
| \`anthropic/claude-sonnet-4.5\` | 3.1500 | 15.7500 | 1,000,000 | chat, code  |
| \`openai/gpt-5.6-terra-pro\` | 2.6250 | 15.7500 | 1,050,000 | chat, code  |
| \`openai/gpt-5.6-luna-pro\` | 1.0500 | 6.3000 | 1,050,000 | chat, code  |
| \`openai/gpt-5.5\` | 5.2500 | 31.5000 | 1,050,000 | chat, code  |
| \`anthropic/claude-opus-4.5\` | 5.2500 | 26.2500 | 200,000 | chat, code  |
| \`anthropic/claude-opus-4.7\` | 5.2500 | 26.2500 | 1,000,000 | chat, code  |
| \`anthropic/claude-opus-4.8\` | 5.2500 | 26.2500 | 1,000,000 | chat, code  |
| \`openai/gpt-5.3-codex\` | 1.8375 | 14.7000 | 400,000 | chat  |
| \`anthropic/claude-fable-5\` | 10.5000 | 52.5000 | 1,000,000 | chat  |
| \`anthropic/claude-opus-4.6\` | 5.2500 | 26.2500 | 1,000,000 | chat  |
| \`kwaipilot/kat-coder-air-v2.5\` | 0.1575 | 0.6300 | 256,000 | code, chat, tool_use |
| \`kwaipilot/kat-coder-pro-v2.5\` | 0.7770 | 3.1080 | 256,000 | code, chat, tool_use |
| \`nex-agi/nex-n2-mini\` | 0.0263 | 0.1050 | 262,144 | code, chat, tool_use |
| \`thinkingmachines/inkling\` | 0.00105 | 0.00425 | 1,048,576 | chat, code |
| \`moonshotai/kimi-k3\` | 0.00315 | 0.01575 | 1,000,000 | chat, reasoning |
| \`meta/muse-spark-1.1\` | 0.00131 | 0.00446 | 1,048,576 | chat, code, multimodal |

### C. Image Generation Models
| Model ID | Input Cost (credits/1K) | Output Cost (credits/1K) | Context Window | Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| \`krea/krea-2-medium-turbo\` | 0.0000 | 0.01575 | 100,000 | image_generation  |
| \`krea/krea-2-medium\` | 0.0000 | 0.03150 | 100,000 | image_generation  |
| \`krea/krea-2-large\` | 0.0000 | 0.06300 | 100,000 | image_generation  |
| \`black-forest-labs/flux.2-flex\` | 0.0000 | 0.0306 | 100,000 | image_generation  |
| \`black-forest-labs/flux.2-max\` | 0.0000 | 0.0510 | 100,000 | image_generation  |
| \`black-forest-labs/flux.2-klein-4b\` | 0.0000 | 0.0102 | 100,000 | image_generation  |
| \`sourceful/riverflow-v2-fast\` | 0.0000 | 0.0102 | 100,000 | image_generation  |
| \`sourceful/riverflow-v2-pro\` | 0.0000 | 0.0357 | 100,000 | image_generation  |
| \`sourceful/riverflow-v2.5-fast\` | 0.0000 | 0.0102 | 100,000 | image_generation  |
| \`google/gemini-3-pro-image-preview\` | 0.0000 | 12.6000 | 65,536 | image_generation  |
| \`google/gemini-3.1-flash-image-preview\` | 0.0000 | 3.1500 | 131,072 | chat, image  |
| \`google/gemini-3.1-flash-image\` | 0.0000 | 3.1500 | 131,072 | image_generation  |
| \`openai/gpt-5-image-mini\` | 0.0000 | 2.1000 | 400,000 | image_generation  |
| \`openai/gpt-image-2\` | 0.0204 | 0.0204 | 100,000 | image_generation  |
| \`recraft/recraft-v4.1\` | 0.0000 | 0.0357 | 100,000 | image_generation  |
| \`recraft/recraft-v4.1-pro\` | 0.0000 | 0.2142 | 100,000 | image_generation  |
| \`recraft/recraft-v4.1-utility\` | 0.0000 | 0.0357 | 100,000 | image_generation  |
| \`recraft/recraft-v4.1-utility-pro\` | 0.0000 | 0.3060 | 100,000 | image_generation  |
| \`recraft/recraft-v4.1-vector\` | 0.0000 | 0.0816 | 100,000 | image_generation  |
| \`recraft/recraft-v4.1-pro-vector\` | 0.0000 | 0.3060 | 100,000 | image_generation  |
| \`x-ai/grok-imagine-image-quality\` | 0.0000 | 0.0408 | 100,000 | image_generation  |
| \`microsoft/mai-image-2.5\` | 0.0000 | 0.0204 | 100,000 | image_generation  |
| \`sourceful/riverflow-v2.5-pro\` | 0.0000 | 0.0408 | 100,000 | image_generation  |
| \`black-forest-labs/flux.2-pro\` | 0.0000 | 0.0306 | 100,000 | image_generation  |
| \`bytedance-seed/seedream-4.5\` | 0.0000 | 0.0408 | 100,000 | image_generation  |
| \`recraft/recraft-v3\` | 0.0000 | 0.0408 | 100,000 | image_generation  |
| \`recraft/recraft-v4\` | 0.0000 | 0.0408 | 100,000 | image_generation  |
| \`recraft/recraft-v4-pro\` | 0.0000 | 0.2550 | 100,000 | image_generation  |
| \`recraft/recraft-v4-vector\` | 0.0000 | 0.0816 | 100,000 | image_generation  |
| \`recraft/recraft-v4-pro-vector\` | 0.0000 | 0.3060 | 100,000 | image_generation  |
| \`google/gemini-3-pro-image\` | 0.0000 | 12.6000 | 65,536 | image_generation  |
| \`openai/gpt-image-1\` | 0.0020 | 0.0020 | 100,000 | image_generation  |
| \`openai/gpt-image-1-mini\` | 0.0005 | 0.0005 | 100,000 | image_generation  |
| \`google/gemini-2.5-flash-image\` | 0.0000 | 2.6250 | 32,768 | image_generation  |
| \`openai/gpt-5-image\` | 0.0000 | 10.5000 | 400,000 | image_generation  |
    `
  },
  'quickstart': {
    title: 'Quickstart',
    content: `
# Quickstart Guide

Use this guide to install UTIM, authenticate it, open a project, run the first task, and recover safely if something goes wrong.

## 1. Install

\`\`\`bash
npm install -g @emend-ai/utim
\`\`\`

If you are running from the Python source tree instead of the npm wrapper:

\`\`\`bash
pip install .
pip install ".[full]"
\`\`\`

The full install enables optional search, image, and tree-sitter parser features.

## 2. Verify the command

\`\`\`bash
utim --version
utim doctor
\`\`\`

\`utim doctor\` checks Python, required packages, optional packages, local config, UTIM API reachability, OpenRouter reachability, and MCP command paths.

## 3. Sign in

\`\`\`bash
utim login
\`\`\`

Inside an interactive UTIM session you can also type:

\`\`\`text
/login
\`\`\`

Login stores account credentials in the UTIM config. Logout clears credentials while keeping preferences and custom model settings:

\`\`\`bash
utim logout
\`\`\`

## 4. Open a workspace

\`\`\`bash
cd my-project
utim
\`\`\`

On startup UTIM creates \`.utim/\` if needed. This workspace directory stores local database state, project rules, default skills, session state, and config overrides.

## 5. Run your first request

Good first prompts are scoped and verifiable:

\`\`\`text
Fix the failing auth test and run the smallest relevant test.
Add a README section documenting local development commands.
Refactor the pricing card component without changing visible behavior.
\`\`\`

For a one-shot non-interactive task:

\`\`\`bash
utim task "Update the README with install and troubleshooting instructions"
\`\`\`

## 6. Start safely

Use dry-run when exploring a large repository:

\`\`\`bash
utim --dry-run
utim task "Find dead code in the API layer" --dry-run
\`\`\`

Use sandbox mode when command execution needs stricter review:

\`\`\`bash
utim --sandbox
\`\`\`

## 7. Recover changes

Inside UTIM:

| Command | Use |
| --- | --- |
| \`/undo\` | Revert the last agent-applied action. |
| \`/redo\` | Re-apply the last undone action. |
| \`/rewind\` | Restore to a previous conversation turn. |
| \`/new\` | Start a fresh session and clear active state. |
| \`/report\` | Create a redacted support bundle under \`.utim_tmp/\`. |

## 8. Daily setup checklist

- Start UTIM from the project root.
- Run \`utim doctor\` after fresh installs or dependency changes.
- Use \`/model\` to choose the active model and custom providers.
- Use \`/tools\` to disable tools you do not want the agent to call.
- Keep project rules in \`.utim/AGENTS.md\`, \`.utim/UTIM.md\`, or \`.agents/skills\`.
    `
  },
  'changelog': {
    title: 'Changelog',
    content: `
# Changelog

The website changelog tab fetches release notes from the UTIM backend when available. This reference explains what release notes mean and how to validate your installed CLI.

## Check your installed version

\`\`\`bash
utim --version
\`\`\`

Inside the terminal UI:

\`\`\`text
/about
\`\`\`

The source package version is defined in \`pyproject.toml\`. Website display versions, backend release feeds, and CLI about text should be kept synchronized during releases.

## What a UTIM release usually contains

| Area | Examples |
| --- | --- |
| Agent loop | Planning behavior, tool-call parsing, self-healing, prompt routing. |
| Terminal UI | Dialogs, keybindings, command completion, status bars, scroll handling. |
| Safety | Undo/redo reliability, sandbox rules, dry-run behavior, sensitive data redaction. |
| Models | New hosted models, custom provider behavior, subagent model choices. |
| MCP | Registry updates, server launch fixes, schema handling, stdio cleanup. |
| Billing | Plan visibility, quota math, credit display, checkout and top-up fixes. |
| Website | Docs, pricing, auth, profile, support chat, release notes. |

## Pre-upgrade checklist

- Save work and commit unrelated local changes.
- Run \`/report\` if you are debugging a failing install before upgrading.
- Note your active model and custom provider settings.
- Run \`utim doctor\` after upgrading.
- Open a small test repository and run a harmless dry-run prompt.

## Post-upgrade smoke test

\`\`\`bash
utim --version
utim doctor
utim task "Read the README and summarize the project structure" --dry-run
\`\`\`

## Release quality expectations

Before a release is business-ready, it should pass:

- Landing site production build.
- Python test suite.
- CLI import smoke test.
- Login/logout smoke test.
- Docs rendering check for tables and code blocks.
- Quota and billing API smoke tests.
- Package install verification for the public install path.
    `
  },
  'how-it-works': {
    title: 'How UTIM Works',
    content: `
# How UTIM Works

UTIM is an agent loop, not an autocomplete engine. It reads the workspace, reasons about the requested outcome, edits files, runs commands, observes results, and keeps rollback state.

## Execution lifecycle

| Stage | What happens |
| --- | --- |
| Prompt intake | UTIM receives a natural-language task from interactive chat or \`utim task\`. |
| Bootstrap context | Workspace rules, local skills, config, model settings, and session state are loaded. |
| Discovery | Files, directories, tests, package metadata, and project conventions are inspected. |
| Planning | The agent forms a checklist or internal execution plan. |
| Tool execution | Built-in tools and MCP tools read files, patch files, run commands, search, or analyze assets. |
| Validation | Syntax checks and selected tests/build commands are run when appropriate. |
| Persistence | Messages, turn history, undo snapshots, and token usage are stored locally. |
| Recovery | \`/undo\`, \`/redo\`, and \`/rewind\` use saved state to restore files. |

## Context sources

UTIM can use:

- The current working directory.
- \`.utim/config.json\` and global \`~/.utim/config.json\`.
- \`.utim/AGENTS.md\`, \`.utim/UTIM.md\`, and \`.utim/analytical_rules.md\`.
- \`.utim/skills/*/SKILL.md\` and \`.agents/skills/*/SKILL.md\`.
- Session history and active turn state.
- Optional vector memory and reflection records.
- MCP server schemas and external tool results.

## Editing strategy

The agent prefers targeted edits over full rewrites when possible:

- \`read_file\` for file inspection.
- \`edit_file\` for precise replacements.
- \`write_file\` for new files or complete generated content.
- Syntax validation for supported file types before writes.
- Backup snapshots before mutating operations.

## Command execution

\`run_command\` supports timeouts, working directories, dry-run mode, and sandbox checks. In interactive mode, risky operations can ask for confirmation. In non-interactive mode, UTIM avoids blocking forever on prompts.

## Self-healing

When a build, test, or syntax check fails, UTIM can feed the error back into the model and patch the cause. Regression loops are controlled by config and environment flags, so high-cost verification is not forced on every request.

## What remains under your control

- Which model is active.
- Which tools are enabled.
- Whether dry-run or sandbox mode is used.
- Whether to approve risky commands.
- When to undo or rewind.
- Which external MCP servers are connected.
    `
  },
  'extend-code': {
    title: 'Extend UTIM (MCP)',
    content: `
# Extend UTIM CLI with MCP

Model Context Protocol (MCP) lets UTIM expose external tools to the agent through standard server processes. Use it when the agent needs structured access to systems that are not built into the CLI.

## Common use cases

- Query a local SQLite or PostgreSQL database.
- Inspect GitHub repositories, issues, or pull requests.
- Read files through a constrained filesystem server.
- Connect search, browser automation, design, or productivity tools.
- Add internal company tools without modifying UTIM core code.

## Configure servers

Inside UTIM:

\`\`\`text
/mcp
\`\`\`

The MCP manager can install, update, list, and connect configured servers. Server definitions are stored in local config such as \`.utim/mcp.json\`.

## Toggle exposed tools

\`\`\`text
/tools
\`\`\`

The tools dialog lets you enable or disable built-in tools and MCP tools. This matters because MCP tools can access external systems depending on the server configuration.

## Example server categories

| Category | Example capability |
| --- | --- |
| Database | Inspect schema, run read queries, analyze migrations. |
| Repository | Review issues, inspect PRs, summarize branches. |
| Filesystem | Read/write only explicitly allowed folders. |
| Browser | Use Playwright-style automation and page inspection. |
| Search | Retrieve web or documentation results. |
| Internal API | Call company-specific workflows through a custom MCP server. |

## MCP health checks

Run:

\`\`\`bash
utim doctor
\`\`\`

Doctor reads MCP config and checks whether configured commands exist on the machine. If a server does not start, check:

- The command exists on \`PATH\`.
- Required environment variables are present.
- API tokens are valid.
- The server logs to stderr, not stdout, when using stdio transport.
- The server exits cleanly on EOF.

## Security notes

MCP servers run locally with the permissions you grant them. Prefer least-privilege tokens, project-scoped database credentials, and filesystem allowlists. Disable unused MCP tools from \`/tools\`.
    `
  },
  'utim-dir': {
    title: 'Explore the .utim_tmp Directory',
    content: `
# Explore \`.utim\` and \`.utim_tmp\`

UTIM uses two local workspace directories: \`.utim/\` for persistent project state and \`.utim_tmp/\` for temporary artifacts, backups, and support outputs.

## \`.utim/\`

Persistent local state.

| Path | Purpose |
| --- | --- |
| \`.utim/config.json\` | Project-level config overrides. |
| \`.utim/utim_local.db\` | Local SQLite database for users and conversations. |
| \`.utim/session_state.json\` | Active session restoration state. |
| \`.utim/AGENTS.md\` | Generated project-scoped rules. |
| \`.utim/UTIM.md\` | Generated default agent identity and operating rules. |
| \`.utim/analytical_rules.md\` | Generated analysis framework. |
| \`.utim/skills/\` | Local skill files used for RAG context. |
| \`.utim/vector_db/\` | Persistent ChromaDB vector store when enabled. |
| \`.utim/mcp.json\` | Local MCP server configuration when configured. |

## \`.utim_tmp/\`

Temporary and diagnostic state.

| Path | Purpose |
| --- | --- |
| \`.utim_tmp/backups/\` | File snapshots for undo, redo, and rewind. |
| \`.utim_tmp/knowledge_graph.json\` | Generated code relationship graph when parser features are used. |
| \`.utim_tmp/vector_meta_*.json\` | Metadata for indexed vector collections. |
| \`.utim_tmp/report_bundle.zip\` | Redacted support report generated by \`/report\`. |

## Global config

UTIM also uses:

\`\`\`text
~/.utim/
\`\`\`

Global config stores account credentials, custom models, preferences, and logs. Local config overrides global config for project-specific behavior.

## What can be deleted

- Use \`utim reset\` for a safer reset of \`.utim/\`.
- Use \`/new\` to clear active session state without deleting the project cache manually.
- Do not manually delete \`.utim_tmp/backups/\` if you still need undo or rewind for the current session.

## Business backup guidance

For teams, do not commit \`.utim/\` or \`.utim_tmp/\` unless you intentionally want to version project rules. Generated databases, credentials, reports, and backups should stay out of Git.
    `
  },
  'context-window': {
    title: 'Explore the Context Window',
    content: `
# Explore the Context Window

The context window is the amount of text the active model can consider in one request. UTIM manages that space by combining current task context, recent turns, relevant files, tool results, and compressed memory.

## What enters context

- System instructions and safety rules.
- User prompt and recent conversation turns.
- Relevant project files read by the agent.
- Tool outputs such as command logs or test failures.
- Local project rules from \`.utim/AGENTS.md\`, \`.utim/UTIM.md\`, and skills.
- Retrieved memory from vector databases when enabled.
- MCP tool schemas and results.

## Why pruning is needed

Large repositories and long sessions can exceed model token limits. UTIM estimates token pressure and removes lower-value material first while keeping the newest user requests, important errors, and technical evidence.

## Importance scoring

| Content type | Typical treatment |
| --- | --- |
| User messages | Preserved with high priority. |
| Tool calls | Kept when needed for schema and execution continuity. |
| Tracebacks and errors | High priority because they explain failures. |
| Code snippets | Higher priority than generic conversation. |
| Old low-signal replies | First candidates for pruning. |

## Compression

When pruning would discard too much useful information, UTIM can ask a fallback model to compress older content into a dense technical summary. This preserves facts such as files changed, commands run, errors seen, and decisions made.

## Controls

| Setting | Purpose |
| --- | --- |
| \`UTIM_KEEP_TURNS\` | Number of recent turns to keep fully. |
| \`UTIM_COMPRESSION\` | Enables or disables compression. |
| \`UTIM_FALLBACK_MODELS\` | Comma-separated fallback models for compression and recovery. |

## Practical tips

- Mention exact file paths when you know them.
- Ask for a focused change instead of a broad rewrite.
- Use \`/clear\` or \`/new\` when a session has drifted.
- Keep project rules concise and specific.
- Run targeted tests so command output stays useful.
    `
  },
  'prompt-caching': {
    title: 'Prompt Caching',
    content: `
# Prompt Caching and Context Reuse

UTIM reduces repeated context work by persisting local state, reusing project rules, retrieving memories, and keeping active session history. Provider-side prompt caching may also apply depending on the selected model route.

## What UTIM reuses locally

- Active conversation state.
- Turn history and redo history.
- Project rules and generated skills.
- Custom model configuration.
- Vector memory collections.
- Knowledge graph artifacts.
- Reflections and feedback-derived lessons.

## What model providers may cache

Some model routes support caching repeated prompt prefixes. This can reduce latency or cost when the same large system prompt, project rules, or context prefix repeats across turns. Exact caching behavior depends on the selected provider and model.

## What is not guaranteed

- Cache hits are not guaranteed across all providers.
- Changing model, system instructions, or project context can invalidate reuse.
- Sensitive or private data should not be placed in prompts solely to benefit from caching.

## How to improve reuse

- Keep stable project rules in \`.utim/AGENTS.md\` or \`.utim/skills\`.
- Avoid pasting the same large document repeatedly.
- Let UTIM read files from disk instead of manually pasting file contents.
- Use focused requests so prior context remains relevant.
- Use \`/new\` only when you truly want to discard session continuity.

## Troubleshooting stale context

If UTIM appears to remember obsolete facts:

\`\`\`text
/new
/clear
\`\`\`

For deeper local reset:

\`\`\`bash
utim reset
\`\`\`
    `
  },
  'instructions': {
    title: 'Store Instructions & Memories',
    content: `
# Store Instructions & Memories

UTIM can load persistent project guidance from generated \`.utim\` files and workspace skill files. This lets you teach the agent conventions once instead of repeating them in every prompt.

## Primary instruction files

| File | Purpose |
| --- | --- |
| \`.utim/AGENTS.md\` | Project-scoped rules and skill routing guidance. |
| \`.utim/UTIM.md\` | Default agent identity and operating mindset. |
| \`.utim/analytical_rules.md\` | Goal-first analysis framework. |
| \`.utim/skills/*/SKILL.md\` | Domain-specific reusable instructions. |
| \`.agents/skills/*/SKILL.md\` | Workspace-level skills that can be shared outside \`.utim\`. |

## What to put in instructions

Good instructions are specific, testable, and stable:

- Preferred package manager.
- Test commands for backend, frontend, and full suite.
- Styling conventions.
- Architecture boundaries.
- Files that should not be edited.
- Deployment constraints.
- Security rules.
- Review checklist.

## Example project rule

\`\`\`md
# Project Rules

- Use npm for frontend commands.
- Run npm.cmd run build from landing/ before shipping website changes on Windows.
- Do not edit generated dist assets by hand.
- Keep docs in landing/src/docs_md and visible docs content in TerminalWidgets.jsx synchronized.
\`\`\`

## Skill files

A skill is a folder containing \`SKILL.md\`. UTIM scans \`.utim/skills\` and \`.agents/skills\`, extracts descriptions and keywords, and injects relevant skill content when the user prompt matches.

## Memory and reflection

When optional memory features are enabled, successful and failed task patterns can be stored as local experiences. Similar future prompts can retrieve these lessons through semantic search.

## Keep instructions healthy

- Keep rules short enough to be useful.
- Remove stale setup instructions.
- Prefer exact commands over vague advice.
- Separate frontend, backend, CLI, and deployment rules into focused skills.
    `
  },
  'permission-modes': {
    title: 'Permission Modes',
    content: `
# Permission Modes

UTIM can read files, write files, and run commands. Permission modes control how much friction is applied before those actions happen.

## Main modes

| Mode | How to use | Behavior |
| --- | --- | --- |
| Interactive default | \`utim\` | Full terminal UI, confirmations where needed, slash commands available. |
| Task mode | \`utim task "<prompt>"\` | Runs one task and exits. |
| Dry-run | \`utim --dry-run\` or \`utim task ... --dry-run\` | Simulates file edits and command execution. |
| Sandbox | \`utim --sandbox\` or \`utim task ... --sandbox\` | Classifies risky commands and blocks or confirms them. |

## Tool controls

Inside UTIM:

\`\`\`text
/tools
\`\`\`

Use the tools dialog to enable or disable:

- File editing tools.
- Shell command tools.
- Web search.
- Image tools.
- Blender tools.
- MCP-provided tools.

## Risk examples

| Action | Recommended mode |
| --- | --- |
| Reading and summarizing docs | Default or dry-run. |
| Editing one README file | Default. |
| Refactoring many files | Default with careful review, or dry-run first. |
| Running tests | Default. |
| Installing packages | Sandbox or explicit confirmation. |
| Deleting files | Manual review required. |
| Running unknown shell scripts | Sandbox first. |

## Non-interactive behavior

When stdin is not a TTY, UTIM avoids blocking indefinitely on prompt dialogs. This matters for scripts, CI jobs, and piped inputs.

## Security recommendations

- Start in dry-run for unfamiliar repositories.
- Disable tools you do not need.
- Use least-privilege API keys for MCP integrations.
- Review commands that install, delete, upload, or change credentials.
- Keep \`.utim/\` and \`.utim_tmp/\` out of public repositories.
    `
  },
  'manage-sessions': {
    title: 'Manage Sessions',
    content: `
# Manage Sessions

UTIM stores active conversation and rollback state so work can continue after a restart and so changes can be reverted.

## Session commands

| Command | Purpose |
| --- | --- |
| \`/resume\` | Open the session browser and load previous conversations. |
| \`/chatrestore\` | Toggle automatic startup restoration. |
| \`/new\` | Start a fresh session and remove active restore state. |
| \`/clear\` | Clear current visible conversation and active turn history. |
| \`/status\` | Show active session statistics. |

## What is persisted

- Conversation messages.
- Turn history.
- Redo history.
- Token usage counters.
- Active session topic.
- File-change snapshots.
- Current model information.

## Storage

Session data is stored in \`.utim/utim_local.db\` and active restoration data can be stored in \`.utim/session_state.json\`.

## Undo stack

The undo system is tied to turn history:

- \`/undo\` restores files changed by the most recent agent action.
- \`/redo\` re-applies a previously undone action.
- \`/rewind\` returns to a selected earlier turn.

## When to start fresh

Use \`/new\` when:

- The task direction changed completely.
- The context has become noisy.
- You loaded the wrong session.
- You want startup to stop restoring the current work.

Use \`/clear\` when:

- You want a cleaner current screen.
- You do not need visible history for the next prompt.

## Team workflow

Before sharing or escalating:

- Run \`/status\`.
- Run \`/report\` for a support bundle.
- Use \`/share\` when you need to package chat and workspace context.
- Commit or stash unrelated work before large agent changes.
    `
  },
  'workflows': {
    title: 'Common Workflows',
    content: `
# Common Workflows

These examples show how to phrase tasks so UTIM can act, verify, and recover cleanly.

## Feature development

\`\`\`text
Add a password reset flow. Inspect the existing auth routes first, reuse current email utilities, and run the smallest relevant backend tests.
\`\`\`

Expected behavior:

- Inspect auth structure.
- Find existing email/token patterns.
- Patch backend and frontend files.
- Run targeted tests.
- Summarize changed files and verification.

## Bug fixing

\`\`\`text
Fix the checkout TypeError shown in the test output. Do not refactor unrelated billing code.
\`\`\`

Good bug prompts include:

- Error message.
- Failing command.
- Expected behavior.
- Files or modules you suspect.
- Refactor boundaries.

## Refactoring

\`\`\`text
Refactor the API client into a service module while preserving all public function names. Run existing API client tests.
\`\`\`

Refactor rules:

- State what must not change.
- Ask for targeted tests.
- Avoid mixing formatting churn with behavior changes.
- Use \`/undo\` if the blast radius becomes too large.

## Documentation

\`\`\`text
Expand the docs page with installation, commands, config, safety, MCP, and troubleshooting. Build the landing site after editing.
\`\`\`

Documentation tasks should specify audience and source of truth.

## UI polishing

\`\`\`text
Fix docs table rendering on mobile and desktop. Keep the terminal theme and verify production build.
\`\`\`

For UI work, ask UTIM to check:

- Layout overflow.
- Mobile behavior.
- Text wrapping.
- Build output.
- Visual regressions when screenshots are available.

## Safe exploration

\`\`\`bash
utim task "Analyze the repository architecture and list risky areas" --dry-run
\`\`\`

Use dry-run for audits, migrations, and unfamiliar codebases before allowing writes.
    `
  },
  'integrations-overview': {
    title: 'Overview',
    content: `
# Platforms & Integrations Overview

UTIM has a local CLI surface, hosted account services, website surfaces, and extension points through MCP and model providers.

## Surfaces

| Surface | Purpose |
| --- | --- |
| Local CLI | Main developer agent that reads, edits, runs, and verifies code locally. |
| Task command | One-shot automation through \`utim task\`. |
| Website | Docs, pricing, auth, profile, support, changelog, and checkout surfaces. |
| Backend API | Auth, usage, quota, releases, support chat, billing, and share flows. |
| MCP servers | External tools such as databases, GitHub, filesystem, search, and automation. |
| Model providers | Hosted UTIM routing, OpenRouter, and custom OpenAI-compatible providers. |

## Local-first model

The CLI runs on the user's machine. It can access local files and commands according to the permissions of the current user and UTIM's active safety mode.

Hosted services are used for:

- Authentication.
- Quota and billing.
- Model routing when using UTIM-hosted credentials.
- Release metadata.
- Support chat.
- Share links.

## Integration rules

- Use \`/mcp\` for tool integrations.
- Use \`/model\` for model/provider integrations.
- Use environment variables for deployment-specific overrides.
- Use \`.utim/\` for project-local state.
- Use \`~/.utim/\` for global user state.

## Business integration checklist

- Verify SSO/auth requirements.
- Document which source code or prompts are sent to model providers.
- Use least-privilege tokens for MCP.
- Create support and incident response paths.
- Run CLI smoke tests on each supported operating system.
    `
  },
  'web-desktop': {
    title: 'Web & Desktop Apps',
    content: `
# Web & Desktop Interfaces

The website is the public and account-management layer for UTIM. The actual code agent remains the local CLI.

## Website pages

| Page | Purpose |
| --- | --- |
| \`/\` | Terminal-style home experience and product entry. |
| \`/features\` | Capability overview. |
| \`/pricing\` | Plan selection and checkout entry. |
| \`/docs\` | Full documentation and policy viewer. |
| \`/changelog\` | Release feed from the backend when available. |
| \`/support\` and \`/contacts\` | Support and contact paths. |
| \`/auth\` | Sign-in and sign-up. |
| \`/profile\` | Authenticated account and subscription details. |
| \`/privacy\`, \`/terms\`, \`/license\`, \`/refund\` | Legal and policy pages. |

## Support assistant

The website support chat is constrained to answer UTIM and website questions. It reads local markdown page content through a tool before answering, so docs quality directly affects support quality.

## Billing surfaces

The pricing and profile pages integrate with hosted subscription and checkout APIs. The CLI also exposes billing-related commands:

\`\`\`bash
utim usage
utim quota
utim plan
utim billing
utim upgrade
\`\`\`

## Install surface

The website currently advertises:

\`\`\`bash
npm install -g @emend-ai/utim
\`\`\`

The source repository also supports Python installation from checkout.

## Business readiness concerns

- Keep website pricing and CLI plan commands synchronized.
- Keep docs and support assistant source documents synchronized.
- Add E2E tests for auth, profile, checkout, docs, and support chat.
- Reduce bundle size through code splitting before heavy marketing launch.
- Ensure legal pages match actual data flow and billing behavior.
    `
  },
  'ci-cd': {
    title: 'Code Review & CI/CD',
    content: `
# Code Review & CI/CD

UTIM can be used in automation through task mode, but CI/CD usage should be configured conservatively because the agent can edit files and run commands.

## One-shot task mode

\`\`\`bash
utim task "Run the test suite and fix the smallest obvious failure" --dry-run
\`\`\`

For CI, start with dry-run or analysis-only prompts. Allow write access only in controlled workflows.

## Recommended CI stages

| Stage | Command |
| --- | --- |
| Landing build | \`cd landing && npm.cmd run build\` on Windows or \`npm run build\` on Unix. |
| Python tests | \`pytest\` or targeted test subsets. |
| CLI smoke | \`utim --version\` and \`utim doctor\`. |
| Docs smoke | Build website and inspect docs page rendering. |
| Package smoke | Install package in a clean environment and run \`utim --version\`. |

## Safe automation pattern

1. Run UTIM in dry-run mode for diagnosis.
2. Save output as CI artifact.
3. Let a developer review proposed changes.
4. Apply fixes in a controlled branch.
5. Run normal test and build gates.

## Pull request review workflow

Good prompt:

\`\`\`text
Review this branch for regressions. Focus on changed files, failing tests, security-sensitive code, and missing docs. Do not edit files.
\`\`\`

Good fix prompt:

\`\`\`text
Fix the failing docs table rendering test only. Do not change unrelated UI layout.
\`\`\`

## Secrets and credentials

- Do not expose production secrets to agent runs.
- Use least-privilege service tokens.
- Redact logs before uploading artifacts.
- Keep \`.utim/\`, \`.utim_tmp/\`, and support bundles out of public CI artifacts unless reviewed.

## Business release gates

Before tagging a release:

- Landing build passes.
- Python tests pass.
- CLI smoke test passes on supported operating systems.
- Docs render tables and code blocks correctly.
- Login, quota, billing, and checkout flows pass in staging.
- Changelog and visible version are synchronized.
    `
  },
  'privacy': {
    title: 'Privacy Policy',
    content: privacyMd
  },
  'terms': {
    title: 'Terms of Service',
    content: termsMd
  },
  'refund': {
    title: 'Refund Policy',
    content: refundMd
  },
  'license': {
    title: 'Proprietary License',
    content: licenseMd
  }
};

const isMarkdownTableSeparator = (line) => {
  const trimmed = line.trim();
  if (!trimmed.includes('|')) return false;
  return /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(trimmed);
};

const parseMarkdownTable = (lines) => {
  const splitRow = (line) => line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map(cell => cell.trim());

  return {
    headers: splitRow(lines[0]),
    rows: lines.slice(2).map(splitRow)
  };
};

const DocsMarkdown = ({ content }) => {
  const blocks = [];
  const lines = (content || '').split('\n');
  let textBuffer = [];
  let inCodeFence = false;

  const flushText = () => {
    if (textBuffer.length) {
      blocks.push({ type: 'markdown', content: textBuffer.join('\n') });
      textBuffer = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.trim().startsWith('```')) {
      inCodeFence = !inCodeFence;
      textBuffer.push(line);
      continue;
    }

    if (!inCodeFence && line.trim().startsWith('|') && isMarkdownTableSeparator(lines[i + 1] || '')) {
      flushText();
      const tableLines = [line, lines[i + 1]];
      i += 2;
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        tableLines.push(lines[i]);
        i++;
      }
      i--;
      blocks.push({ type: 'table', ...parseMarkdownTable(tableLines) });
      continue;
    }

    textBuffer.push(line);
  }

  flushText();

  return blocks.map((block, index) => {
    if (block.type === 'table') {
      return (
        <div className="tw-markdown-table-wrapper" key={index}>
          <table className="tw-markdown-table">
            <thead>
              <tr>
                {block.headers.map((header, headerIndex) => (
                  <th key={headerIndex}>{header}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {block.headers.map((_, cellIndex) => (
                    <td key={cellIndex}>{row[cellIndex] || ''}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    return <ReactMarkdown key={index}>{block.content}</ReactMarkdown>;
  });
};

export const InlineDocs = ({ initialArticle }) => {
  const [activeArticle, setActiveArticle] = useState(initialArticle || 'overview');

  useEffect(() => {
    if (initialArticle) {
      setActiveArticle(initialArticle);
    }
  }, [initialArticle]);

  return (
    <div className="tw-widget tw-docs-widget">
      <h3 className="tw-widget-title tw-docs-title">U.T.I.M DOCUMENTATION & MANUAL</h3>
      
      <div className="tw-docs-layout">
        
        {/* Left Sidebar Navigation */}
        <div className="tw-docs-sidebar">
          {DOCS_TREE.map(cat => (
            <div className="tw-docs-nav-group" key={cat.category}>
              <h5 className="tw-docs-nav-heading">{cat.category}</h5>
              <div className="tw-docs-nav-items">
                {cat.items.map(item => (
                  <button
                    key={item.id}
                    onClick={() => setActiveArticle(item.id)}
                    className={`tw-docs-nav-button ${activeArticle === item.id ? 'active' : ''}`}
                  >
                    {item.title}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Right Scrollable Content Panel */}
        <div className="tw-docs-content-shell">
          <motion.div
            key={activeArticle}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.15 }}
            className="tw-docs-tab-content tw-markdown-content"
          >
            {activeArticle === 'models-pricing' ? (
              <ModelsPricingDoc />
            ) : (
              <DocsMarkdown content={DOCS_ARTICLES[activeArticle]?.content || ''} />
            )}
          </motion.div>
        </div>

      </div>
    </div>
  );
};

const highlightsData = [
  {
    title: "Dedicated Subagent Fleet",
    desc: "Spawns specialized workers on demand: Image Generation, Blender Agent, Web Search Agent, Planning Agent, and Synthetic Eye (enabling visual parsing for non-vision LLMs).",
    tag: "Subagents",
    color: "#00F0FF"
  },
  {
    title: "Experience DB & Situational Scoring",
    desc: "Learns from past coding trajectories. Situational scoring retrieves historical experiences using a local vector database to make the agent smarter with negligible token usage.",
    tag: "Cognitive Memory",
    color: "#E5FF00"
  },
  {
    title: "Absolute Tool & Sandbox Control",
    desc: "You retain full control. Enable, disable, lock, or restrict specific CLI commands, system tools, and custom MCP connections dynamically on a per-session basis.",
    tag: "Tool Permissions",
    color: "#00FF66"
  },
  {
    title: "Unused Quota Rollover",
    desc: "Unused monthly credits roll over automatically for up to 2 months. No waste of paid compute budgets—you get what you paid for.",
    tag: "Rollover Billing",
    color: "#FF8C00"
  },
  {
    title: "Zero-Pollution Revert Stack",
    desc: "Logs every package, file edit, and command locally. Run /undo or /rewind at any time to cleanly revert files back to any checkpoint.",
    tag: "/undo & /rewind",
    color: "#FF4C8B"
  },
  {
    title: "No-Gate Custom BYOK Models",
    desc: "Connect any OpenAI-compatible provider. Custom models bypass subscription quota limits entirely, run on custom endpoints, and persist across project workspaces.",
    tag: "BYOK Engine",
    color: "#B266FF"
  }
];

const comparisonData = [
  {
    feature: "Specialized agent workers",
    utim: "Built-in Image, Web and Blender workers",
    cursor: "Supports configurable subagents",
    copilot: "Supports custom agents and subagent delegation",
    chatgpt: "Supports subagent workflows; availability varies by surface"
  },
  {
    feature: "Local scored experience retrieval",
    utim: "Local experience DB with situational scoring",
    cursor: "Persistent rules; no documented equivalent architecture",
    copilot: "Copilot Memory, but not documented as a local scored DB",
    chatgpt: "Saved memory/history, but not a local scored experience DB"
  },
  {
    feature: "Per-tool controls",
    utim: "Tool-level enablement and policies",
    cursor: "MCP toggles, permissions and allowlists",
    copilot: "Custom-agent tool lists and CLI permissions",
    chatgpt: "Codex permissions and app/tool controls"
  },
  {
    feature: "Unused allowance rollover",
    utim: "Up to two months, subject to UTIM terms",
    cursor: "Verify current plan terms",
    copilot: "No monthly carryover",
    chatgpt: "Feature limits reset; purchased-credit expiry rules apply"
  },
  {
    feature: "Multi-file rollback",
    utim: "Transactional /undo stack",
    cursor: "Avoid claiming no rollback without testing",
    copilot: "/undo and /rewind supported",
    chatgpt: "Git checkpoint workflow; no equivalent transaction command confirmed"
  },
  {
    feature: "BYOK",
    utim: "Bypasses UTIM-hosted model quotas; provider limits remain",
    cursor: "Supported",
    copilot: "Supported on relevant surfaces",
    chatgpt: "Supported by local Codex; regular ChatGPT web is different"
  }
];

export const InlineInstallation = () => {
  const [copiedNpm, setCopiedNpm] = useState(false);
  const [copiedCd, setCopiedCd] = useState(false);
  const [copiedUtim, setCopiedUtim] = useState(false);
  const [copiedNpx, setCopiedNpx] = useState(false);
  const [copiedPip, setCopiedPip] = useState(false);

  const handleCopy = (text, setFn) => {
    navigator.clipboard.writeText(text);
    setFn(true);
    setTimeout(() => setFn(false), 2000);
  };

  return (
    <div className="tw-install-section">
      <div className="tw-install-banner">
        <div className="tw-install-header">
          <span className="tw-install-tag">[FULL SETUP PROCESS]</span>
          <h2 className="tw-install-title">How to Install & Run UTIM CLI</h2>
          <p className="tw-install-subtitle">
            Follow this step-by-step guide to install UTIM CLI locally and start building apps directly from your terminal.
          </p>
        </div>

        {/* Main NPM Copy Card */}
        <div className="tw-install-main-card">
          <div className="tw-install-badge-row">
            <span className="tw-install-recommended">RECOMMENDED INSTALLATION</span>
            <span className="tw-install-env">Available for Windows and Mac. Android (Termux) coming soon</span>
          </div>
          <div className="tw-install-cmd-box">
            <span className="tw-install-prompt">$</span>
            <code className="tw-install-code">npm install -g @emend-ai/utim</code>
            <button 
              className="tw-install-copy-btn"
              onClick={() => handleCopy("npm install -g @emend-ai/utim", setCopiedNpm)}
            >
              {copiedNpm ? '✓ Copied!' : 'Copy NPM Command'}
            </button>
          </div>
        </div>

        {/* Notice Callout Box: Web Chat vs CLI Agent */}
        <div className="tw-notice-callout-box">
          <div className="tw-notice-icon">💡</div>
          <div className="tw-notice-content">
            <strong>Web Support Chat vs Local CLI Agent:</strong> The chat interface on this website is our <em>Web Support Assistant</em> for Q&A and site navigation. To let UTIM edit your codebase, spawn dev servers, and run autonomous agent loops, follow the 4 steps below in your terminal!
          </div>
        </div>

        {/* 4-Step Setup Grid */}
        <div className="tw-install-steps-grid">
          <div className="tw-install-step-card">
            <div>
              <div className="tw-step-num">STEP 01</div>
              <h3>1. Open Terminal</h3>
              <p>Launch PowerShell, Command Prompt, or Terminal on your computer.</p>
            </div>
            <div className="tw-step-code-pill" style={{ cursor: 'default' }}>
              <code>Terminal / PowerShell</code>
              <span style={{ color: '#00FF66' }}>Ready</span>
            </div>
          </div>

          <div className="tw-install-step-card">
            <div>
              <div className="tw-step-num">STEP 02</div>
              <h3>2. Run npm Install</h3>
              <p>Execute global install command to download UTIM CLI agent.</p>
            </div>
            <div className="tw-step-code-pill" onClick={() => handleCopy("npm install -g @emend-ai/utim", setCopiedNpm)}>
              <code>npm install -g @emend-ai/utim</code>
              <span>{copiedNpm ? '✓ Copied' : 'Copy'}</span>
            </div>
          </div>

          <div className="tw-install-step-card">
            <div>
              <div className="tw-step-num">STEP 03</div>
              <h3>3. cd Project Folder</h3>
              <p>Navigate into your codebase folder or create a new empty directory.</p>
            </div>
            <div className="tw-step-code-pill" onClick={() => handleCopy("cd your-project-folder", setCopiedCd)}>
              <code>cd your-project-folder</code>
              <span>{copiedCd ? '✓ Copied' : 'Copy'}</span>
            </div>
          </div>

          <div className="tw-install-step-card">
            <div>
              <div className="tw-step-num">STEP 04</div>
              <h3>4. Run "utim" & Build</h3>
              <p>Type <code>utim</code> in terminal to start the agent and begin building!</p>
            </div>
            <div className="tw-step-code-pill" onClick={() => handleCopy("utim", setCopiedUtim)}>
              <code>utim</code>
              <span>{copiedUtim ? '✓ Copied' : 'Copy'}</span>
            </div>
          </div>
        </div>

        {/* Alternative Package Managers */}
        <div className="tw-install-alt-grid">
          <div className="tw-alt-card">
            <span className="tw-alt-label">NPX (Zero Install):</span>
            <div className="tw-alt-cmd" onClick={() => handleCopy("npx @emend-ai/utim", setCopiedNpx)}>
              <code>npx @emend-ai/utim</code>
              <span className="tw-alt-btn">{copiedNpx ? '✓ Copied' : 'Copy'}</span>
            </div>
          </div>

          <div className="tw-alt-card">
            <span className="tw-alt-label">Python Package:</span>
            <div className="tw-alt-cmd" onClick={() => handleCopy("pip install utim-cli", setCopiedPip)}>
              <code>pip install utim-cli</code>
              <span className="tw-alt-btn">{copiedPip ? '✓ Copied' : 'Copy'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export const InlineHighlights = () => {
  return (
    <div className="term-markdown-view">
      <motion.div 
        className="term-md-header"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="term-md-tag">[THE UNFAIR ADVANTAGE]</div>
        <div className="term-md-title"># Why UTIM CLI stands out</div>
        <div className="term-md-subtitle">
          Other coding assistants require manual copying, pasting, and running packages.
          UTIM CLI operates locally, visualizes layout changes, and reverts code transactions cleanly.
        </div>
      </motion.div>

      <div className="term-md-divider">================================================================================</div>

      {/* CLI Installation Section */}
      <InlineInstallation />

      <div className="term-md-section-title">## Core Advantages</div>
      <div className="term-md-highlights-list">
        {highlightsData.map((h, i) => (
          <motion.div 
            key={h.title} 
            className="term-md-card"
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.08, duration: 0.2 }}
          >
            <div className="term-md-card-border-top">┌── {h.tag} ──────────────────────────────────────</div>
            <div className="term-md-card-content">
              <span className="term-md-bullet">■</span> <strong className="term-md-highlight-title" style={{ color: h.color }}>{h.title}</strong>
              <p className="term-md-highlight-desc">{h.desc}</p>
            </div>
            <div className="term-md-card-border-bottom">└─────────────────────────────────────────────────</div>
          </motion.div>
        ))}
      </div>

      <div className="term-md-section-title">## Feature Comparison Matrix</div>
      
      <motion.div 
        className="term-md-table-wrapper"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4, duration: 0.3 }}
      >
        <table className="term-md-table">
          <thead>
            <tr>
              <th>CAPABILITY</th>
              <th className="term-md-th-highlight">UTIM CLI</th>
              <th>CURSOR</th>
              <th>GITHUB COPILOT</th>
              <th>CHATGPT / CODEX</th>
            </tr>
          </thead>
          <tbody>
            {comparisonData.map((row, idx) => (
              <tr key={idx}>
                <td className="term-md-td-feature">{row.feature}</td>
                <td className="term-md-td-utim">{row.utim}</td>
                <td className="term-md-td-other">{row.cursor}</td>
                <td className="term-md-td-other">{row.copilot}</td>
                <td className="term-md-td-other">{row.chatgpt}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </motion.div>
    </div>
  );
};

const REFERRAL_PLAN_LABELS = {
  hobby:    { name: 'Hobbyist Node',    color: '#ec4899', price_usd: '$7/mo',   price_inr: 'Rs.700/mo'   },
  starter:  { name: 'Starter Node',     color: '#00F0FF', price_usd: '$25/mo',  price_inr: 'Rs.2500/mo'  },
  professional: { name: 'Professional Core', color: '#e8c97a', price_usd: '$55/mo',  price_inr: 'Rs.5500/mo'  },
  ultimate: { name: 'MAX Node',         color: '#00FF66', price_usd: '$110/mo', price_inr: 'Rs.11000/mo' },
};

export const InlineReferral = () => {
  const { user, getToken, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const isIndian = detectIsIndian();

  const [referralInfo, setReferralInfo] = useState(null);
  const [leaderboard, setLeaderboard]   = useState([]);
  const [loading, setLoading]           = useState(true);
  const [copiedUrl, setCopiedUrl]       = useState(false);
  const [copiedCode, setCopiedCode]     = useState(false);
  const [linkInput, setLinkInput]       = useState('');
  const [linkStatus, setLinkStatus]     = useState(null); // null | 'loading' | 'success' | 'error'
  const [linkMsg, setLinkMsg]           = useState('');

  const handleLinkCode = async () => {
    if (!linkInput.trim()) return;
    setLinkStatus('loading');
    setLinkMsg('');
    try {
      const token  = await getToken();
      const apiUrl = getApiUrl();
      const res    = await fetch(`${apiUrl}/api/rewards/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ referral_code: linkInput.trim() }),
      });
      const data = await res.json();
      if (res.ok) {
        setLinkStatus('success');
        setLinkMsg('Referral code linked! Reload to see your referrer.');
        setLinkInput('');
        // refresh info
        const infoRes  = await fetch(`${apiUrl}/api/rewards/info`, { headers: { Authorization: `Bearer ${token}` } });
        const info     = await infoRes.json();
        setReferralInfo(info);
      } else {
        setLinkStatus('error');
        setLinkMsg(data.detail || 'Failed to link code.');
      }
    } catch (err) {
      setLinkStatus('error');
      setLinkMsg('Network error. Please try again.');
    }
  };

  useEffect(() => {
    if (!user) { setLoading(false); return; }
    const fetchAll = async () => {
      try {
        const token  = await getToken();
        const apiUrl = getApiUrl();
        const [infoRes, boardRes] = await Promise.all([
          fetch(`${apiUrl}/api/rewards/info`,        { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${apiUrl}/api/rewards/leaderboard`, { headers: { Authorization: `Bearer ${token}` } }),
        ]);
        const info  = await infoRes.json();
        const board = await boardRes.json();
        setReferralInfo(info);
        setLeaderboard(board.leaderboard || []);
      } catch (err) {
        console.error('referral fetch error', err);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, [user]);

  const copyUrl = () => {
    if (!referralInfo) return;
    navigator.clipboard.writeText(referralInfo.referral_url);
    setCopiedUrl(true);
    setTimeout(() => setCopiedUrl(false), 2000);
  };

  const copyCode = () => {
    if (!referralInfo) return;
    navigator.clipboard.writeText(referralInfo.referral_code);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const totalDiscount = referralInfo
    ? Object.values(referralInfo.discounts || {}).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <div className="term-markdown-view">
      <motion.div
        className="term-md-header"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="term-md-tag" style={{ color: '#00FF66' }}>[REFERRAL PROTOCOL ACTIVE]</div>
        <div className="term-md-title"># Earn Free Access by Sharing UTIM</div>
        <div className="term-md-subtitle">
          Share your unique link. Every referred purchase adds a{' '}
          <span style={{ color: '#00FF66', fontWeight: 'bold' }}>2% discount</span> on that plan — stacking up to{' '}
          <span style={{ color: '#00FF66', fontWeight: 'bold' }}>100% off</span>.
        </div>
      </motion.div>

      <div className="term-md-divider">================================================================================</div>

      {/* How It Works */}
      <motion.div
        className="term-md-card"
        style={{ marginBottom: '24px', borderColor: 'rgba(0,255,102,0.2)', background: 'rgba(0,255,102,0.02)' }}
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}
      >
        <div style={{ color: '#00FF66', fontWeight: 'bold', fontSize: '0.85rem', padding: '12px 16px', borderBottom: '1px solid rgba(0,255,102,0.1)', fontFamily: 'monospace' }}>
          [HOW THE REFERRAL ENGINE WORKS]
        </div>
        <div style={{ padding: '16px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '16px' }}>
          {[
            { step: '01', title: 'Share Your Link',   desc: 'Send your unique referral URL to other developers.' },
            { step: '02', title: 'They Subscribe',    desc: 'Referred user purchases any paid plan.' },
            { step: '03', title: 'You Earn 2% Off',   desc: 'Discount is plan-specific — different plans stack independently.' },
            { step: '04', title: 'Stack to 100%',     desc: 'Each referee purchase/renewal adds a 2% discount up to 100% off your next bill. Applied discounts reset to 0% after purchase.' },
          ].map(({ step, title, desc }) => (
            <div key={step} style={{ display: 'flex', gap: '12px' }}>
              <div style={{ color: '#00FF66', fontFamily: 'monospace', fontSize: '1.1rem', fontWeight: 'bold', minWidth: '28px' }}>{step}</div>
              <div>
                <div style={{ color: '#fff', fontWeight: 'bold', fontSize: '0.82rem', marginBottom: '4px' }}>{title}</div>
                <div style={{ color: '#888', fontSize: '0.78rem', lineHeight: '1.5' }}>{desc}</div>
              </div>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Example callout */}
      <div className="term-md-card" style={{ marginBottom: '24px', borderColor: 'rgba(0,240,255,0.12)' }}>
        <div style={{ color: '#00F0FF', fontWeight: 'bold', fontSize: '0.85rem', padding: '10px 16px', borderBottom: '1px solid rgba(0,240,255,0.08)', fontFamily: 'monospace' }}>
          [EXAMPLE SCENARIO]
        </div>
        <div style={{ padding: '12px 16px', color: '#888', fontSize: '0.8rem', lineHeight: '1.9', fontFamily: 'monospace' }}>
          <span style={{ color: '#00F0FF' }}>You</span> refer B, C, D ...<br />
          → B buys <span style={{ color: '#ec4899' }}>Hobbyist</span> → you get <span style={{ color: '#00FF66' }}>2% off Hobbyist</span><br />
          → C buys <span style={{ color: '#ec4899' }}>Hobbyist</span> → now <span style={{ color: '#00FF66' }}>4% off Hobbyist</span><br />
          → D buys <span style={{ color: '#00F0FF' }}>Starter</span> → you also get <span style={{ color: '#00FF66' }}>2% off Starter</span><br />
          → B <span style={{ color: '#555' }}>renews</span> next month → <span style={{ color: '#00FF66' }}>6% off Hobbyist</span> (stacks again)<br />
          → You purchase the plan → discount is consumed and applied to your bill<br />
          → After purchase, your discount resets to 0% and starts stacking again when a referred user renews or a new referee purchases the same plan.
        </div>
      </div>

      {/* Auth gate */}
      {!isAuthenticated ? (
        <div className="term-md-card" style={{ textAlign: 'center', padding: '32px', marginBottom: '24px' }}>
          <div style={{ color: '#e74856', fontFamily: 'monospace', marginBottom: '8px' }}>[AUTHENTICATION REQUIRED]</div>
          <div style={{ color: '#aaa', fontSize: '0.85rem', marginBottom: '20px' }}>Sign in to access your referral dashboard and unique link.</div>
          <button
            className="tw-pricing-btn"
            style={{ borderColor: 'rgba(0,240,255,0.3)', color: '#00F0FF', maxWidth: '240px', margin: '0 auto' }}
            onClick={() => navigate('/auth?mode=signup')}
          >
            &gt; AUTHENTICATE()
          </button>
        </div>
      ) : loading ? (
        <div style={{ textAlign: 'center', color: '#555', padding: '40px', fontFamily: 'monospace' }}>
          Fetching referral data...
        </div>
      ) : referralInfo && (
        <>
          {/* Link referral code — for existing users who signed up before entering a code */}
          {referralInfo && !referralInfo.referred_by && (
            <motion.div
              className="term-md-card"
              style={{ marginBottom: '24px', borderColor: 'rgba(0,240,255,0.2)', background: 'rgba(0,240,255,0.02)' }}
              initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.18 }}
            >
              <div style={{ color: '#00F0FF', fontWeight: 'bold', padding: '12px 16px', borderBottom: '1px solid rgba(0,240,255,0.1)', fontFamily: 'monospace', fontSize: '0.85rem' }}>
                [LINK A REFERRAL CODE]
              </div>
              <div style={{ padding: '16px' }}>
                <div style={{ color: '#666', fontSize: '0.8rem', marginBottom: '12px', fontFamily: 'monospace' }}>
                  Were you referred by someone? Enter their code to link the referral.
                </div>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                  <input
                    type="text"
                    value={linkInput}
                    onChange={e => { setLinkInput(e.target.value); setLinkStatus(null); setLinkMsg(''); }}
                    onKeyDown={e => e.key === 'Enter' && handleLinkCode()}
                    placeholder="Enter referral code (e.g. a3f9b2c1)"
                    disabled={linkStatus === 'loading'}
                    style={{
                      flex: 1, minWidth: '200px',
                      background: 'rgba(0,240,255,0.04)',
                      border: '1px solid rgba(0,240,255,0.2)',
                      borderRadius: '6px',
                      padding: '8px 12px',
                      color: '#fff',
                      fontFamily: 'monospace',
                      fontSize: '0.9rem',
                      letterSpacing: '2px',
                      outline: 'none',
                    }}
                  />
                  <button
                    className="tw-pricing-btn"
                    style={{ padding: '8px 16px', borderColor: 'rgba(0,240,255,0.3)', color: '#00F0FF', whiteSpace: 'nowrap', opacity: linkStatus === 'loading' ? 0.5 : 1 }}
                    onClick={handleLinkCode}
                    disabled={linkStatus === 'loading'}
                  >
                    {linkStatus === 'loading' ? 'LINKING...' : '> LINK CODE'}
                  </button>
                </div>
                {linkMsg && (
                  <div style={{ marginTop: '10px', fontFamily: 'monospace', fontSize: '0.78rem', color: linkStatus === 'success' ? '#00FF66' : '#e74856' }}>
                    {linkStatus === 'success' ? '✓ ' : '[!] '}{linkMsg}
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {/* Referral credentials */}
          <motion.div
            className="term-md-card"
            style={{ marginBottom: '24px', borderColor: 'rgba(0,255,102,0.25)' }}
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
          >
            <div style={{ color: '#00FF66', fontWeight: 'bold', padding: '12px 16px', borderBottom: '1px solid rgba(0,255,102,0.1)', fontFamily: 'monospace', fontSize: '0.85rem' }}>
              [YOUR REFERRAL CREDENTIALS]
            </div>
            <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <div style={{ color: '#444', fontSize: '0.72rem', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '6px' }}>Referral Code</div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <code style={{ background: 'rgba(0,255,102,0.06)', padding: '7px 14px', borderRadius: '6px', color: '#00FF66', fontFamily: 'monospace', fontSize: '1rem', letterSpacing: '3px', border: '1px solid rgba(0,255,102,0.2)' }}>
                    {referralInfo.referral_code}
                  </code>
                  <button
                    className="tw-pricing-btn"
                    style={{ fontSize: '0.78rem', padding: '7px 14px', borderColor: 'rgba(0,255,102,0.3)', color: '#00FF66' }}
                    onClick={copyCode}
                  >
                    {copiedCode ? '✓ COPIED' : 'COPY CODE'}
                  </button>
                </div>
              </div>
              <div>
                <div style={{ color: '#444', fontSize: '0.72rem', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '6px' }}>Referral Link</div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <code style={{ background: 'rgba(255,255,255,0.02)', padding: '7px 12px', borderRadius: '6px', color: '#777', fontFamily: 'monospace', fontSize: '0.8rem', border: '1px solid rgba(255,255,255,0.05)', wordBreak: 'break-all', flex: 1, minWidth: '180px' }}>
                    {referralInfo.referral_url}
                  </code>
                  <button
                    className="tw-pricing-btn"
                    style={{ fontSize: '0.78rem', padding: '7px 14px', borderColor: 'rgba(0,255,102,0.3)', color: '#00FF66', whiteSpace: 'nowrap' }}
                    onClick={copyUrl}
                  >
                    {copiedUrl ? '✓ COPIED' : 'COPY LINK'}
                  </button>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Stats row */}
          <motion.div
            style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '24px' }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.25 }}
          >
            {[
              { label: 'Total Referrals',     value: referralInfo.referee_count, color: '#00F0FF' },
              { label: 'Plans with Discount', value: Object.keys(referralInfo.discounts || {}).length, color: '#ec4899' },
              { label: 'Total Discount %',    value: `${Math.min(totalDiscount, 100).toFixed(0)}%`, color: '#00FF66' },
            ].map(({ label, value, color }) => (
              <div key={label} className="term-md-card" style={{ textAlign: 'center', padding: '18px 10px' }}>
                <div style={{ color, fontSize: '1.6rem', fontWeight: 'bold', fontFamily: 'monospace' }}>{value}</div>
                <div style={{ color: '#444', fontSize: '0.72rem', marginTop: '4px', textTransform: 'uppercase' }}>{label}</div>
              </div>
            ))}
          </motion.div>

          {/* Discount breakdown */}
          {Object.keys(referralInfo.discounts || {}).length > 0 && (
            <motion.div
              className="term-md-card"
              style={{ marginBottom: '24px' }}
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}
            >
              <div style={{ color: '#e8c97a', fontWeight: 'bold', padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.04)', fontFamily: 'monospace', fontSize: '0.85rem' }}>
                [ACTIVE DISCOUNT BREAKDOWN]
              </div>
              <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {Object.entries(referralInfo.discounts).map(([planId, pct]) => {
                  // Map backend ID to frontend ID
                  const backendToFrontend = {
                    pro: 'starter',
                    max: 'professional'
                  };
                  const fId = backendToFrontend[planId] || planId;
                  const meta = REFERRAL_PLAN_LABELS[fId] || { name: planId, color: '#aaa', price_usd: '', price_inr: '' };
                  return (
                    <div key={planId}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                        <span style={{ color: meta.color, fontWeight: 'bold', fontSize: '0.85rem' }}>
                          {meta.name}
                          <span style={{ color: '#444', fontWeight: 'normal', marginLeft: '8px', fontSize: '0.75rem' }}>
                            ({isIndian ? meta.price_inr : meta.price_usd})
                          </span>
                        </span>
                        <span style={{ color: '#00FF66', fontFamily: 'monospace', fontWeight: 'bold', fontSize: '0.9rem' }}>
                          {pct >= 100 ? '100% FREE' : `${pct.toFixed(0)}% OFF`}
                        </span>
                      </div>
                      <div style={{ background: 'rgba(255,255,255,0.04)', borderRadius: '3px', height: '5px', overflow: 'hidden' }}>
                        <div style={{ width: `${Math.min(100, pct)}%`, height: '100%', background: pct >= 100 ? '#00FF66' : meta.color, borderRadius: '3px', transition: 'width 0.6s ease' }} />
                      </div>
                      <div style={{ color: '#444', fontSize: '0.72rem', marginTop: '4px', fontFamily: 'monospace' }}>
                        {Math.round(pct / 2)} purchase{Math.round(pct / 2) !== 1 ? 's' : ''} on this plan
                        {pct < 100 && ` · ${Math.ceil((100 - pct) / 2)} more to go FREE`}
                      </div>
                    </div>
                  );
                })}
              </div>
            </motion.div>
          )}

          {/* Referred by notice */}
          {referralInfo.referred_by && (
            <div className="term-md-card" style={{ marginBottom: '24px' }}>
              <div style={{ padding: '10px 16px', color: '#555', fontSize: '0.8rem', fontFamily: 'monospace' }}>
                [INFO] You were referred by{' '}
                <span style={{ color: '#aaa' }}>{referralInfo.referred_by.display_name}</span>{' '}
                ({referralInfo.referred_by.email_hint})
              </div>
            </div>
          )}

          {/* Leaderboard */}
          {leaderboard.length > 0 && (
            <motion.div
              className="term-md-card"
              style={{ marginBottom: '24px' }}
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.35 }}
            >
              <div style={{ color: '#00F0FF', fontWeight: 'bold', padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.04)', fontFamily: 'monospace', fontSize: '0.85rem' }}>
                [TOP REFERRERS LEADERBOARD]
              </div>
              {leaderboard.map((entry) => (
                <div
                  key={entry.rank}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '12px',
                    padding: '10px 16px',
                    borderBottom: '1px solid rgba(255,255,255,0.03)',
                    background: entry.is_me ? 'rgba(0,255,102,0.04)' : 'transparent',
                  }}
                >
                  <div style={{ color: entry.rank <= 3 ? ['#FFD700','#C0C0C0','#CD7F32'][entry.rank - 1] : '#444', fontFamily: 'monospace', fontWeight: 'bold', minWidth: '28px' }}>
                    #{entry.rank}
                  </div>
                  <div style={{ color: entry.is_me ? '#00FF66' : '#aaa', flex: 1, fontSize: '0.85rem', display: 'flex', flexDirection: 'column' }}>
                    <span>{entry.name}{entry.is_me && ' (you)'}</span>
                    {entry.discounts && (
                      <span style={{ fontSize: '0.72rem', color: '#888', marginTop: '2px' }}>
                        Earned Discount: {entry.discounts}
                      </span>
                    )}
                  </div>
                  <div style={{ color: '#00F0FF', fontFamily: 'monospace', fontSize: '0.82rem' }}>
                    {entry.referrals} referral{entry.referrals !== 1 ? 's' : ''}
                  </div>
                </div>
              ))}
            </motion.div>
          )}
        </>
      )}

      <div style={{ color: '#333', fontSize: '0.72rem', textAlign: 'center', marginTop: '16px', fontFamily: 'monospace', lineHeight: '1.6', borderTop: '1px solid rgba(255,255,255,0.03)', paddingTop: '10px' }}>
        [SYSTEM NOTE] Discounts apply per plan at checkout. Max 100% per plan. Renewals stack the discount again. Self-referrals and duplicate accounts are prohibited.
      </div>
    </div>
  );
};

