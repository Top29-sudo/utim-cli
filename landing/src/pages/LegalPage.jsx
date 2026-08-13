import React from 'react';
import ScrollytellingHeaderNav from '../components/ScrollytellingHeaderNav';
import ScrollytellingFooter from '../components/ScrollytellingFooter';
import SEOHead from '../components/SEOHead';
import { ShieldCheck, FileText, RefreshCw, Scale } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import '../components/ScrollytellingMain.css';

export default function LegalPage({ type = 'terms' }) {
  const location = useLocation();
  const currentType = location.pathname.replace('/', '') || type;

  const contentMap = {
    terms: {
      title: "Terms of Service & User Agreement",
      date: "Last Updated: August 9, 2026 • Effective Date: January 1, 2026",
      icon: Scale,
      sections: [
        {
          title: "1. Description of Autonomous CLI Agent Service",
          text: "UTIM ('You Think It, I Make It') is an autonomous developer agent operating inside local software repository directories. Packed as a CLI binary and web client engine, UTIM provides automated code parsing, AST symbol navigation, file creation and patching, terminal command execution, subagent orchestration, and browser testing automation."
        },
        {
          title: "2. Local Execution Risk & Safety Disclaimers",
          text: "Local Command & File Mutation Risk: UTIM executes shell commands and writes files directly on your local system with user authorization. You are solely responsible for reviewing and verifying that instructions, shell commands, and file edits proposed by UTIM are safe for your environment. Emend AI and its contributors shall not be liable for any data loss, source control corruption, hosting or cloud costs, API usage bills, hardware failures, or business damages incurred through autonomous agent operations."
        },
        {
          title: "3. Acceptable Use, Security Boundaries & Anti-Abuse",
          text: "You agree not to use UTIM CLI to generate malware, ransomware, exploits, or malicious payloads; circumvent subscription quotas or rate limits; exploit credit refill mechanisms; run automated unauthorized web scraping against protected systems; create duplicate accounts to harvest signup or promotional credits; or reverse engineer the CLI client orchestrator engine. Abuse or violation of security boundaries will result in immediate permanent account suspension and credit forfeiture."
        },
        {
          title: "4. AI-Generated Code & License Disclaimers",
          text: "AI-generated code and synthesized assets are provided strictly on an 'AS-IS' and 'AS-AVAILABLE' basis without warranty of any kind. UTIM does not guarantee compiler correctness, security, performance, or intellectual property non-infringement status of model completions. Developers are required to review, audit, and run test suites before deploying generated code to staging or production environments."
        },
        {
          title: "5. Subscriptions, Compute Credit Consumption & Refill Rules",
          text: "Model routing consumes compute credits calculated dynamically based on input and output tokens consumed. Subscriptions (Hobby $7/mo, Pro $25/mo, Max $55/mo, Ultimate $110/mo) allocate dedicated compute allowances. Free plan users receive 100 credits auto-refilled every 5 hours (up to 3,000 monthly credits). Paid subscribers receive a 10x priority discount on free models ($0.002 in / $0.003 out per 1M tokens) and non-expiring Rollover Quota Banks. Credit balances and subscription refunds are governed strictly by our Refund Policy."
        },
        {
          title: "6. Intellectual Property & Ownership",
          text: "UTIM, including its CLI binary, brand trademarks, site design, prompt engineering logic, AST indexers, and subagent orchestration engine, is the exclusive intellectual property of Emend AI. Users retain 100% full ownership of all prompts submitted and code files generated within their workspace repositories."
        },
        {
          title: "7. Modifications to Service & Terms",
          text: "We reserve the right to modify, suspend, or discontinue any feature or API route of the Service at any time with prior notice. Continued use of UTIM CLI after term updates constitutes acceptance of revised terms."
        }
      ]
    },
    privacy: {
      title: "Privacy & Data Handling Policy",
      date: "Last Updated: August 9, 2026 • Effective Date: January 1, 2026",
      icon: ShieldCheck,
      sections: [
        {
          title: "1. Information We Collect",
          text: "Account Identity: Email address, Firebase User ID, and optional profile picture/display name. Accounting Telemetry: Token counts consumed per request (input/output tokens), model selection IDs, and active credit balance logs used strictly for billing and refill timers."
        },
        {
          title: "2. Local-First Data Protection (What We NEVER Collect)",
          text: "Source Code & Repository Files: Your project files, source code snippets, and terminal directory contents read by UTIM are processed strictly in-memory during LLM forwarding. We do NOT store, index, or train AI models on your local codebase. Local Vector Database: All ChromaDB embeddings (~/.utim/memory/ and .utim/chroma/) stay 100% on your local disk. We have ZERO server access to your local vector databases."
        },
        {
          title: "3. Local vs. Cloud Data Allocation",
          text: "Local Machine Storage: Local vector embeddings, project configs (.utim/config.json), conversation transcripts (.utim/sessions/), git-tree undo snapshots (.utim_tmp/backups/), and local SQLite databases (.utim/intelligence.db). Cloud Server Storage: Account identity, subscription tier status, usage accounting metrics, and billing logs."
        },
        {
          title: "4. Third-Party Provider Routing & GDPR Rights",
          text: "Prompts sent through OpenRouter or configured model providers follow strict zero-retention policies. We partner with Firebase (auth), Railway (infrastructure), and Razorpay/Stripe (payment gateways). Users retain full GDPR rights to inspect, export, or permanently delete account data."
        },
        {
          title: "5. Data Retention & Account Deletion",
          text: "You may request total account deletion at any time by emailing support@utim.dev or using the CLI /logout command. Account deletion permanently purges all cloud accounting records, Firebase credentials, and subscription logs within 7 business days."
        }
      ]
    },
    refund: {
      title: "Refund & Cancellation Policy",
      date: "Last Updated: August 9, 2026 • Effective Date: January 1, 2026",
      icon: RefreshCw,
      sections: [
        {
          title: "1. 7-Day Subscription Guarantee (Hobby, Pro, Max & Ultimate)",
          text: "All paid subscription plans include a 7-Day Money-Back Guarantee. If you are unsatisfied with your subscription, you may request a full 100% refund within 7 days of initial subscription purchase, provided usage during those 7 days has not exceeded 15 premium model prompts."
        },
        {
          title: "2. Credit Top-Up Packages (Pay-As-You-Go)",
          text: "Only unconsumed, purchased bonus credits remaining in your active credit balance are eligible for pro-rated refunds. Credits already consumed for model completions are permanently non-refundable."
        },
        {
          title: "3. Non-Refundable Items & Promotional Allowances",
          text: "Free promotional credits, referral bonus grants, and 5-hour auto-refill credits have zero monetary cash value and are strictly non-refundable. Accounts suspended for ToS violations forfeit eligibility for refunds."
        },
        {
          title: "4. Step-by-Step Claim Procedure",
          text: "To claim a refund, email support@utim.dev or uthinkimake.official@gmail.com with your account email address, invoice/transaction ID, and reason for cancellation. All valid refund requests are processed within 3-5 business days to original payment methods."
        }
      ]
    },
    license: {
      title: "End User License Agreement (EULA)",
      date: "Last Updated: August 9, 2026 • Effective Date: January 1, 2026",
      icon: FileText,
      sections: [
        {
          title: "1. Software License Grant",
          text: "Subject to the terms of this Agreement, Emend AI grants you a limited, non-exclusive, non-transferable, revocable license to download, install, and execute UTIM CLI on compatible hardware devices (Windows, macOS, Linux, Android Termux)."
        },
        {
          title: "2. Commercial vs. Non-Commercial Usage",
          text: "Free Tier is permitted for open-source development, learning, and personal non-commercial projects. Paid Tiers (Hobby, Pro, Max, Ultimate) or BYOK custom provider key setups are required for commercial software engineering, corporate repositories, and paid freelance client work."
        },
        {
          title: "3. Software Modification & Reverse Engineering Restrictions",
          text: "You may not decompile, reverse engineer, disassemble, decrypt, or attempt to derive source code from compiled UTIM CLI binary distributions or tamper with quota accounting endpoints."
        },
        {
          title: "4. Warranty & Liability Limits",
          text: "UTIM IS PROVIDED 'AS IS' WITHOUT WARRANTY OF ANY KIND. IN NO EVENT SHALL EMEND AI BE LIABLE FOR INCIDENTAL, CONSEQUENTIAL, OR SPECIAL DAMAGES ARISING FROM SOFTWARE INSTALLATION OR AUTONOMOUS CODE EXECUTION."
        }
      ]
    }
  };

  const doc = contentMap[currentType] || contentMap.terms;
  const IconComponent = doc.icon;

  return (
    <div className="st-page-root">
      <SEOHead
        title={`${doc.title} — UTIM AI CLI`}
        description={`Legal terms and guidelines for UTIM AI CLI: ${doc.title}.`}
        canonical={`https://utim.dev/${currentType}`}
      />
      <ScrollytellingHeaderNav />

      <div style={{ padding: '70px 24px 80px 24px', maxWidth: 840, margin: '0 auto' }}>
        <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
          <Link to="/terms" className={`st-tag-item ${currentType === 'terms' ? 'active' : ''}`} style={{ background: currentType === 'terms' ? 'var(--accent-black)' : undefined, color: currentType === 'terms' ? '#fff' : undefined }}>Terms of Service</Link>
          <Link to="/privacy" className={`st-tag-item ${currentType === 'privacy' ? 'active' : ''}`} style={{ background: currentType === 'privacy' ? 'var(--accent-black)' : undefined, color: currentType === 'privacy' ? '#fff' : undefined }}>Privacy Policy</Link>
          <Link to="/refund" className={`st-tag-item ${currentType === 'refund' ? 'active' : ''}`} style={{ background: currentType === 'refund' ? 'var(--accent-black)' : undefined, color: currentType === 'refund' ? '#fff' : undefined }}>Refund Policy</Link>
          <Link to="/license" className={`st-tag-item ${currentType === 'license' ? 'active' : ''}`} style={{ background: currentType === 'license' ? 'var(--accent-black)' : undefined, color: currentType === 'license' ? '#fff' : undefined }}>License</Link>
        </div>

        <div className="st-hero-badge">
          <IconComponent size={14} /> LEGAL & POLICIES
        </div>
        <h1 className="st-section-title" style={{ fontSize: 'clamp(2.4rem, 4.5vw, 3.6rem)', marginBottom: 8 }}>
          {doc.title}
        </h1>
        <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: 36, fontStyle: 'italic' }}>
          {doc.date}
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {doc.sections.map((sec, idx) => (
            <div key={idx} className="st-doc-card">
              <h2 className="st-doc-card-title">{sec.title}</h2>
              <p style={{ fontSize: '0.96rem', color: 'var(--text-body)', lineHeight: 1.7 }}>
                {sec.text}
              </p>
            </div>
          ))}
        </div>
      </div>

      <ScrollytellingFooter />
    </div>
  );
}
