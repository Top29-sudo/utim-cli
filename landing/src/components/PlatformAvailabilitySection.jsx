import React, { useState } from 'react';
import { Monitor, Smartphone, Terminal, Check, Copy, Sparkles, Cpu, Layers } from 'lucide-react';
import './PlatformAvailabilitySection.css';

export default function PlatformAvailabilitySection() {
  const [activeTab, setActiveTab] = useState('android'); // 'windows' | 'mac' | 'android'
  const [copiedId, setCopiedId] = useState(null);

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const platforms = [
    {
      id: 'android',
      name: 'Android (Termux)',
      icon: Smartphone,
      badge: 'Mobile CLI Powerhouse',
      description: 'Run UTIM CLI agents natively on Android smartphones and tablets using Termux with full Node.js, Python & local SQLite support.',
      requirements: ['Termux App (F-Droid / GitHub)', 'Android 7.0+ (ARM64 / x86_64)', 'Node.js 18+ & Python 3.10+'],
      steps: [
        {
          num: '01',
          label: 'Install Dependencies in Termux',
          cmd: 'pkg update -y && pkg install nodejs python -y'
        },
        {
          num: '02',
          label: 'Install UTIM CLI globally',
          cmd: 'npm install -g @emend-ai/utim'
        },
        {
          num: '03',
          label: 'Initialize & Launch Agent',
          cmd: 'utim'
        }
      ]
    },
    {
      id: 'windows',
      name: 'Windows',
      icon: Monitor,
      badge: 'PowerShell & CMD Native',
      description: 'Full Windows terminal integration with automatic PowerShell profile hooks, rich UTF-8 formatting, and background task management.',
      requirements: ['Windows 10 / 11 (64-bit)', 'Node.js 18+ & Python 3.10+', 'PowerShell 7+ or Windows Terminal'],
      steps: [
        {
          num: '01',
          label: 'NPM Global Installation',
          cmd: 'npm install -g @emend-ai/utim'
        },
        {
          num: '02',
          label: 'PowerShell One-Liner (Alternative)',
          cmd: 'iwr https://utim.dev/install.ps1 | iex'
        },
        {
          num: '03',
          label: 'Launch UTIM CLI',
          cmd: 'utim'
        }
      ]
    },
    {
      id: 'mac',
      name: 'macOS & Linux',
      icon: Terminal,
      badge: 'POSIX & zsh/bash Ready',
      description: 'Seamless POSIX terminal support for macOS (Apple Silicon & Intel) and Linux distros with native subprocess stream pipes.',
      requirements: ['macOS 12+ or Ubuntu / Debian / Arch / Fedora', 'Node.js 18+ & Python 3.10+', 'Zsh / Bash'],
      steps: [
        {
          num: '01',
          label: 'NPM Global Installation',
          cmd: 'npm install -g @emend-ai/utim'
        },
        {
          num: '02',
          label: 'cURL Installer (Alternative)',
          cmd: 'curl -fsSL https://utim.dev/install.sh | bash'
        },
        {
          num: '03',
          label: 'Launch UTIM CLI',
          cmd: 'utim'
        }
      ]
    }
  ];

  const currentPlatform = platforms.find(p => p.id === activeTab) || platforms[0];

  return (
    <section className="st-platform-section" id="availability">
      <div className="st-container">
        {/* Section Header */}
        <div className="st-section-header">
          <h2 className="st-section-title">
            Run UTIM CLI Anywhere
          </h2>
          <p className="st-section-subtitle">
            From powerful Windows &amp; Mac developer workstations to pocket-sized Android devices running Termux, UTIM CLI runs everywhere Node.js and Python exist.
          </p>
        </div>

        {/* Platform Tabs */}
        <div className="st-platform-tabs">
          {platforms.map((p) => {
            const Icon = p.icon;
            const isActive = activeTab === p.id;
            return (
              <button
                key={p.id}
                className={`st-platform-tab-btn ${isActive ? 'active' : ''}`}
                onClick={() => setActiveTab(p.id)}
              >
                <Icon size={18} />
                <span>{p.name}</span>
                {p.id === 'android' && <span className="st-tab-highlight">Termux</span>}
              </button>
            );
          })}
        </div>

        {/* Active Platform Card */}
        <div className="st-platform-card">
          <div className="st-platform-header">
            <div className="st-platform-title-group">
              <span className="st-platform-badge-tag">{currentPlatform.badge}</span>
              <h3 className="st-platform-heading">{currentPlatform.name} Installation</h3>
              <p className="st-platform-desc">{currentPlatform.description}</p>
            </div>
          </div>

          <div className="st-platform-body">
            {/* Command Flow Steps */}
            <div className="st-steps-container">
              <h4 className="st-steps-heading">
                <Terminal size={16} /> Recommended Command Flow
              </h4>
              <div className="st-steps-list">
                {currentPlatform.steps.map((step) => {
                  const stepId = `${currentPlatform.id}-${step.num}`;
                  const isCopied = copiedId === stepId;
                  return (
                    <div key={step.num} className="st-step-row">
                      <div className="st-step-num-badge">{step.num}</div>
                      <div className="st-step-content">
                        <span className="st-step-label">{step.label}</span>
                        <div className="st-step-cmd-box">
                          <code>{step.cmd}</code>
                          <button
                            className="st-copy-cmd-btn"
                            onClick={() => handleCopy(step.cmd, stepId)}
                            title="Copy command"
                          >
                            {isCopied ? <Check size={14} className="st-copied-icon" /> : <Copy size={14} />}
                            <span>{isCopied ? 'Copied' : 'Copy'}</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Platform Requirements Sidebar */}
            <div className="st-platform-requirements">
              <h4 className="st-req-heading">
                <Cpu size={16} /> System Requirements
              </h4>
              <ul className="st-req-list">
                {currentPlatform.requirements.map((req, idx) => (
                  <li key={idx}>
                    <Check size={14} className="st-check" />
                    <span>{req}</span>
                  </li>
                ))}
              </ul>

              {currentPlatform.id === 'android' && (
                <div className="st-termux-note">
                  <Layers size={15} style={{ flexShrink: 0, color: '#E5FF00' }} />
                  <div>
                    <strong>Termux Tip:</strong> Install Termux from F-Droid for best package mirror compatibility.
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
