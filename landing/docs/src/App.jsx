import React, { useState } from 'react';
import { docsCategories, platformInstallCommands, slashCommandsList, cliFlagsList, detailedArticles } from './data/docsContent';
import { 
  Terminal, Monitor, Shield, FileCode, Command, Bot, Cpu, 
  Database, RotateCcw, Layers, Sparkles, DollarSign, Gift, 
  Lock, Search, FileText, Share2, RefreshCw, HelpCircle, Scale, 
  ChevronRight, Copy, Check, AlertCircle, ExternalLink, Smartphone, Code,
  BookOpen
} from 'lucide-react';
import './styles.css';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [installPlatform, setInstallPlatform] = useState('windows');
  const [searchQuery, setSearchQuery] = useState('');
  const [copiedId, setCopiedId] = useState(null);

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const filteredCategories = docsCategories.map(cat => ({
    ...cat,
    items: cat.items.filter(item => 
      item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.id.toLowerCase().includes(searchQuery.toLowerCase())
    )
  })).filter(cat => cat.items.length > 0);

  const article = detailedArticles[activeTab] || detailedArticles.overview;

  return (
    <div className="docs-website-root">
      {/* Dedicated Header */}
      <header className="docs-nav-header">
        <a href="https://docs.utim.dev" className="docs-brand-link">
          <img src="/logo.png" alt="UTIM Logo" className="docs-brand-logo" />
          <span>UTIM CLI Documentation</span>
          <span className="docs-license-tag">v2.1.3 PROPRIETARY EULA</span>
        </a>

        <div className="docs-search-wrapper">
          <Search size={16} style={{ position: 'absolute', left: 12, top: 11, color: 'var(--docs-text-muted)' }} />
          <input
            type="text"
            className="docs-search-input"
            placeholder="Search 25+ doc topics, commands, flags..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="docs-header-actions">
          <a href="https://utim.dev" className="docs-ext-link">Main Website</a>
          <a href="https://discord.com/invite/wGB7M8pMEy" target="_blank" rel="noreferrer" className="docs-ext-link">Discord</a>
        </div>
      </header>

      {/* Main Page Layout */}
      <div className="docs-page-grid">
        
        {/* Left Sidebar */}
        <aside className="docs-sidebar">
          {filteredCategories.map((group, idx) => (
            <div key={idx} className="docs-sidebar-section">
              <div className="docs-sidebar-title">{group.title}</div>
              {group.items.map((item) => {
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    className={`docs-nav-button ${isActive ? 'active' : ''}`}
                    onClick={() => setActiveTab(item.id)}
                  >
                    <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.name}</span>
                    <span className="docs-nav-badge">{item.badge}</span>
                  </button>
                );
              })}
            </div>
          ))}
        </aside>

        {/* Center Article Display */}
        <main className="docs-main-article">
          
          <div className="docs-breadcrumb-trail">
            <span>docs.utim.dev</span>
            <ChevronRight size={14} />
            <span>Official Documentation</span>
            <ChevronRight size={14} />
            <span style={{ color: 'var(--docs-text-heading)', fontWeight: 700 }}>{activeTab.toUpperCase()}</span>
          </div>

          <h1 className="docs-h1">{article.title}</h1>
          <p className="docs-lead-text">{article.lead}</p>

          {/* SPECIAL TAB: INSTALLATION */}
          {activeTab === 'installation' && (
            <div style={{ marginTop: 24 }}>
              <div className="docs-tab-bar">
                <button className={`docs-tab-btn ${installPlatform === 'windows' ? 'active' : ''}`} onClick={() => setInstallPlatform('windows')}>
                  <Monitor size={15} inline /> Windows
                </button>
                <button className={`docs-tab-btn ${installPlatform === 'mac' ? 'active' : ''}`} onClick={() => setInstallPlatform('mac')}>
                  <Terminal size={15} inline /> macOS &amp; Linux
                </button>
                <button className={`docs-tab-btn ${installPlatform === 'termux' ? 'active' : ''}`} onClick={() => setInstallPlatform('termux')}>
                  <Smartphone size={15} inline /> Android (Termux)
                </button>
                <button className={`docs-tab-btn ${installPlatform === 'source' ? 'active' : ''}`} onClick={() => setInstallPlatform('source')}>
                  <Code size={15} inline /> Python Source
                </button>
              </div>

              {platformInstallCommands[installPlatform].map((item, idx) => (
                <div key={idx} style={{ marginBottom: 24 }}>
                  <h3 style={{ fontSize: '0.98rem', fontWeight: 700, color: 'var(--docs-text-sub)', marginBottom: 8 }}>{item.title}</h3>
                  <div className="docs-code-box">
                    <div className="docs-code-header">
                      <div className="docs-code-title">
                        <span style={{ color: '#38BDF8' }}>{item.shell}</span>
                      </div>
                      <button className="docs-copy-action" onClick={() => handleCopy(item.cmd, `inst-${installPlatform}-${idx}`)}>
                        {copiedId === `inst-${installPlatform}-${idx}` ? <Check size={14} /> : <Copy size={14} />}
                        {copiedId === `inst-${installPlatform}-${idx}` ? 'Copied!' : 'Copy'}
                      </button>
                    </div>
                    <div className="docs-code-content">
                      <span className="docs-code-prompt">&gt;</span><span style={{ color: '#4ADE80' }}>{item.cmd}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* SPECIAL TAB: SLASH COMMANDS */}
          {activeTab === 'slash-commands' && (
            <div style={{ marginTop: 24 }}>
              <table className="docs-table-grid">
                <thead>
                  <tr>
                    <th style={{ width: '22%' }}>Command</th>
                    <th style={{ width: '15%' }}>Category</th>
                    <th>Operational Action</th>
                    <th style={{ width: '10%' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {slashCommandsList.map((item, idx) => (
                    <tr key={idx}>
                      <td><code style={{ color: '#38BDF8', fontWeight: 700 }}>{item.cmd}</code></td>
                      <td><span style={{ fontSize: '0.75rem', background: '#1E293B', padding: '2px 8px', borderRadius: 4, color: '#CBD5E1' }}>{item.category}</span></td>
                      <td>{item.desc}</td>
                      <td>
                        <button className="docs-copy-action" style={{ position: 'static' }} onClick={() => handleCopy(item.cmd, `sc-${idx}`)}>
                          {copiedId === `sc-${idx}` ? <Check size={12} /> : <Copy size={12} />}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* SPECIAL TAB: CLI FLAGS */}
          {activeTab === 'entrypoints' && (
            <div style={{ marginTop: 24 }}>
              <h2 className="docs-h2">Execution Flags Inspector</h2>
              {cliFlagsList.map((item, idx) => (
                <div key={idx} className="docs-code-box" style={{ margin: '14px 0' }}>
                  <div className="docs-code-header">
                    <code style={{ color: '#38BDF8', fontSize: '0.92rem', fontWeight: 700 }}>{item.flag}</code>
                    <button className="docs-copy-action" onClick={() => handleCopy(item.flag, `flag-${idx}`)}>
                      {copiedId === `flag-${idx}` ? <Check size={14} /> : <Copy size={14} />}
                      {copiedId === `flag-${idx}` ? 'Copied!' : 'Copy'}
                    </button>
                  </div>
                  <div style={{ padding: '14px 18px', fontSize: '0.9rem', color: 'var(--docs-text-body)' }}>
                    {item.desc}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* RENDER DETAILED ARTICLE SECTIONS */}
          {article.sections && article.sections.map((sec, idx) => (
            <div key={idx} style={{ marginTop: 32 }}>
              {sec.heading && <h2 className="docs-h2">{sec.heading}</h2>}
              {sec.text && <p className="docs-paragraph" style={{ whiteSpace: 'pre-line' }}>{sec.text}</p>}

              {sec.callout && (
                <div className={`docs-callout-box ${sec.callout.type || 'info'}`}>
                  <AlertCircle size={22} style={{ flexShrink: 0 }} />
                  <div>
                    <strong>{sec.callout.title}:</strong> {sec.callout.text}
                  </div>
                </div>
              )}

              {sec.code && (
                <div className="docs-code-box">
                  <div className="docs-code-header">
                    <div className="docs-code-title">
                      <span>{sec.code.lang || 'bash'}</span>
                    </div>
                    <button className="docs-copy-action" onClick={() => handleCopy(sec.code.cmd, `sec-code-${idx}`)}>
                      {copiedId === `sec-code-${idx}` ? <Check size={14} /> : <Copy size={14} />}
                      {copiedId === `sec-code-${idx}` ? 'Copied!' : 'Copy'}
                    </button>
                  </div>
                  <div className="docs-code-content" style={{ whiteSpace: 'pre-line' }}>
                    {sec.code.cmd}
                  </div>
                </div>
              )}

              {sec.table && (
                <table className="docs-table-grid">
                  <thead>
                    <tr>
                      <th style={{ width: '30%' }}>Parameter / Feature</th>
                      <th>Operational Specification</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sec.table.map((row, rIdx) => (
                      <tr key={rIdx}>
                        <td><strong style={{ color: '#F8FAFC' }}>{row.key}</strong></td>
                        <td>{row.val}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ))}

        </main>

        {/* Right TOC Sidebar */}
        <aside className="docs-toc-sidebar">
          <div className="docs-toc-heading">On This Page</div>
          {article.sections ? (
            article.sections.map((sec, idx) => (
              <a key={idx} href={`#sec-${idx}`} className="docs-toc-item">
                {sec.heading || `Section ${idx + 1}`}
              </a>
            ))
          ) : (
            <a href="#overview" className="docs-toc-item">Overview</a>
          )}
        </aside>

      </div>
    </div>
  );
}
