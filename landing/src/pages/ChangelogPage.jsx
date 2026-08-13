import React from 'react';
import ScrollytellingHeaderNav from '../components/ScrollytellingHeaderNav';
import ScrollytellingFooter from '../components/ScrollytellingFooter';
import SEOHead from '../components/SEOHead';
import { History as HistoryIcon, CheckCircle2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import '../components/ScrollytellingMain.css';
import rawChangelog from '../../../CHANGELOG.md?raw';

function parseChangelog(mdText) {
  if (!mdText) return [];
  const lines = mdText.split('\n');
  const releases = [];
  let currentRelease = null;

  for (let line of lines) {
    const trimmed = line.trim();
    // Header format: ## [2.1.2] - 2026-08-10 or ## [2.0.1] - 2026-08-04 - Subtitle
    const headerMatch = trimmed.match(/^##\s+\[?([^\]\s]+)\]?\s*-\s*([0-9]{4}-[0-9]{2}-[0-9]{2})(?:\s*-\s*(.*))?/);
    if (headerMatch) {
      if (currentRelease && currentRelease.items.length > 0) {
        releases.push(currentRelease);
      }
      const rawVersion = headerMatch[1];
      const versionStr = rawVersion.startsWith('v') ? rawVersion : `v${rawVersion}`;
      const dateStr = headerMatch[2];
      const extraTitle = headerMatch[3] ? headerMatch[3].trim() : '';

      let formattedDate = dateStr;
      try {
        const [y, m, d] = dateStr.split('-').map(Number);
        const dateObj = new Date(Date.UTC(y, m - 1, d));
        formattedDate = dateObj.toLocaleDateString('en-US', {
          month: 'long',
          day: 'numeric',
          year: 'numeric',
          timeZone: 'UTC'
        });
      } catch (e) {
        // fallback to dateStr
      }

      currentRelease = {
        version: extraTitle ? `${versionStr} — ${extraTitle}` : versionStr,
        date: formattedDate,
        items: []
      };
      continue;
    }

    if (currentRelease && trimmed.startsWith('- ')) {
      const itemText = trimmed.replace(/^-\s+/, '');
      if (itemText) {
        currentRelease.items.push(itemText);
      }
    }
  }

  if (currentRelease && currentRelease.items.length > 0) {
    releases.push(currentRelease);
  }

  return releases;
}

export default function ChangelogPage() {
  const releases = parseChangelog(rawChangelog);

  return (
    <div className="st-page-root">
      <SEOHead
        title="Changelog & Release Notes — UTIM AI CLI"
        description="Chronological release notes, updates, bug fixes, and improvements to UTIM AI CLI."
        canonical="https://utim.dev/changelog"
      />
      <ScrollytellingHeaderNav />

      <div style={{ padding: '70px 24px 80px 24px', maxWidth: 840, margin: '0 auto' }}>
        <div className="st-hero-badge">
          <HistoryIcon size={14} /> RELEASE NOTES & HISTORY
        </div>
        <h1 className="st-section-title" style={{ fontSize: 'clamp(2.4rem, 4.5vw, 3.6rem)', marginBottom: 20 }}>
          UTIM CLI Changelog
        </h1>
        <p className="st-section-subtitle" style={{ marginBottom: 40 }}>
          Continuous improvements, feature releases, and optimizations deployed to the UTIM terminal ecosystem.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {releases.map((rel, idx) => (
            <div key={idx} className="st-doc-card">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14, flexWrap: 'wrap', gap: 8 }}>
                <span style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-primary)', fontFamily: 'JetBrains Mono' }}>
                  {rel.version}
                </span>
                <span style={{ fontSize: '12.5px', fontWeight: 700, color: 'var(--text-muted)', background: 'var(--bg-cream-alt)', padding: '4px 10px', borderRadius: 100, border: '1px solid var(--border-cream)' }}>
                  {rel.date}
                </span>
              </div>
              <ul style={{ listStyle: 'none', fontSize: '0.94rem', color: 'var(--text-body)', lineHeight: 1.7, padding: 0, margin: 0 }}>
                {rel.items.map((item, iIdx) => (
                  <li key={iIdx} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 8 }}>
                    <CheckCircle2 size={16} color="var(--accent-green)" style={{ flexShrink: 0, marginTop: 4 }} />
                    <div style={{ flex: 1 }}>
                      <ReactMarkdown
                        components={{
                          p: ({ node, ...props }) => <span style={{ margin: 0 }} {...props} />,
                          code: ({ node, inline, ...props }) => (
                            <code style={{ background: 'rgba(255,255,255,0.08)', padding: '2px 6px', borderRadius: 4, fontFamily: 'JetBrains Mono', fontSize: '0.85em' }} {...props} />
                          )
                        }}
                      >
                        {item}
                      </ReactMarkdown>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      <ScrollytellingFooter />
    </div>
  );
}
