import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { getApiUrl } from '../../lib/api';
import '../../components/PowershellUI/PowershellUI.css';

const PLAN_LABELS = {
  hobby: { name: 'Hobbyist Node', color: '#ec4899', price_usd: '$7', price_inr: 'Rs.700' },
  pro:   { name: 'Starter Node',  color: '#00F0FF', price_usd: '$25', price_inr: 'Rs.2500' },
  max:   { name: 'Professional Core',  color: '#e8c97a', price_usd: '$55', price_inr: 'Rs.5500' },
  ultimate: { name: 'MAX Node',   color: '#00FF66', price_usd: '$110', price_inr: 'Rs.11000' },
};

const ReferralPage = () => {
  const { user, getToken } = useAuth();
  const navigate = useNavigate();

  const [referralInfo, setReferralInfo] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [copiedCode, setCopiedCode] = useState(false);

  useEffect(() => {
    if (!user) return;
    const fetchData = async () => {
      try {
        const token = await getToken();
        const apiUrl = getApiUrl();

        const [infoRes, boardRes] = await Promise.all([
          fetch(`${apiUrl}/api/referrals/info`, { headers: { 'Authorization': `Bearer ${token}` } }),
          fetch(`${apiUrl}/api/referrals/leaderboard`, { headers: { 'Authorization': `Bearer ${token}` } }),
        ]);
        const infoData = await infoRes.json();
        const boardData = await boardRes.json();
        setReferralInfo(infoData);
        setLeaderboard(boardData.leaderboard || []);
      } catch (err) {
        console.error('Referral fetch error:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [user]);

  const copyUrl = () => {
    if (!referralInfo) return;
    navigator.clipboard.writeText(referralInfo.referral_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
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
    <div className="term-wrapper">
      <div className="term-window" style={{ maxWidth: '900px' }}>
        {/* Titlebar */}
        <div className="term-titlebar">
          <div className="term-tab" onClick={() => navigate('/')}>
            <span className="term-tab-icon" style={{ color: '#3b78ff' }}>&gt;_</span>
            <span className="term-tab-title">Home</span>
          </div>
          <div className="term-tab active">
            <span className="term-tab-icon" style={{ color: '#00FF66' }}>%</span>
            <span className="term-tab-title">Referral Program</span>
          </div>
          <div className="term-window-controls">
            <div className="term-ctrl">_</div>
            <div className="term-ctrl">□</div>
            <div className="term-ctrl close" onClick={() => navigate('/')}>×</div>
          </div>
        </div>

        <div className="term-content term-markdown-view" style={{ padding: '32px' }}>
          {/* Header */}
          <div className="term-md-header" style={{ marginBottom: '24px' }}>
            <div className="term-md-tag" style={{ color: '#00FF66' }}>[REFERRAL PROTOCOL ACTIVE]</div>
            <h1 className="term-md-title" style={{ fontSize: '1.6rem', margin: '8px 0' }}>
              # Earn Free Access by Sharing UTIM
            </h1>
            <div className="term-md-subtitle" style={{ color: '#aaa', fontSize: '0.9rem', lineHeight: '1.6' }}>
              Share your unique referral link. Every time a referred developer buys a plan,
              you automatically earn a <span style={{ color: '#00FF66', fontWeight: 'bold' }}>2% perpetual discount</span> on
              that same plan — stacking up to <span style={{ color: '#00FF66', fontWeight: 'bold' }}>100% free</span>.
            </div>
          </div>

          <div className="term-md-divider">================================================================================</div>

          {/* How It Works */}
          <div className="term-md-card" style={{ marginBottom: '24px', borderColor: 'rgba(0,255,102,0.2)', background: 'rgba(0,255,102,0.02)' }}>
            <div style={{ color: '#00FF66', fontWeight: 'bold', fontSize: '0.85rem', padding: '12px 16px', borderBottom: '1px solid rgba(0,255,102,0.1)', fontFamily: 'monospace' }}>
              [HOW THE REFERRAL ENGINE WORKS]
            </div>
            <div style={{ padding: '16px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
              {[
                { step: '01', title: 'Share Your Link', desc: 'Send your unique referral URL to other developers. They sign up via your link.' },
                { step: '02', title: 'They Subscribe', desc: 'When a referred user purchases any paid plan, the discount engine triggers.' },
                { step: '03', title: 'You Earn 2% Off', desc: 'You get a 2% discount on that exact plan. Discount is plan-specific, not global.' },
                { step: '04', title: 'Stack to 100%', desc: '50 referrals on the same plan = 100% free. Renewals stack the discount again.' },
              ].map(({ step, title, desc }) => (
                <div key={step} style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                  <div style={{ color: '#00FF66', fontFamily: 'monospace', fontSize: '1.2rem', fontWeight: 'bold', minWidth: '32px' }}>
                    {step}
                  </div>
                  <div>
                    <div style={{ color: '#fff', fontWeight: 'bold', fontSize: '0.85rem', marginBottom: '4px' }}>{title}</div>
                    <div style={{ color: '#888', fontSize: '0.8rem', lineHeight: '1.5' }}>{desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Example breakdown */}
          <div className="term-md-card" style={{ marginBottom: '24px', borderColor: 'rgba(0,240,255,0.15)', background: 'rgba(0,240,255,0.02)' }}>
            <div style={{ color: '#00F0FF', fontWeight: 'bold', fontSize: '0.85rem', padding: '10px 16px', borderBottom: '1px solid rgba(0,240,255,0.1)', fontFamily: 'monospace' }}>
              [EXAMPLE SCENARIO]
            </div>
            <div style={{ padding: '14px 16px', color: '#aaa', fontSize: '0.82rem', lineHeight: '1.8', fontFamily: 'monospace' }}>
              <div><span style={{ color: '#00F0FF' }}>User A</span> refers users B, C, D ...</div>
              <div>→ B purchases <span style={{ color: '#ec4899' }}>Hobbyist</span> → A gets <span style={{ color: '#00FF66' }}>2% off Hobbyist</span></div>
              <div>→ C purchases <span style={{ color: '#ec4899' }}>Hobbyist</span> → A now has <span style={{ color: '#00FF66' }}>4% off Hobbyist</span></div>
              <div>→ D purchases <span style={{ color: '#00F0FF' }}>Starter</span> → A also gets <span style={{ color: '#00FF66' }}>2% off Starter</span></div>
              <div>→ B <span style={{ color: '#aaa' }}>renews</span> Hobbyist next month → A gets <span style={{ color: '#00FF66' }}>+2% more = 6% off Hobbyist</span></div>
              <div style={{ marginTop: '8px', color: '#555' }}>Discounts are applied automatically at checkout. Max 100% per plan.</div>
            </div>
          </div>

          {/* Auth gate */}
          {!user ? (
            <div className="term-md-card" style={{ marginBottom: '24px', textAlign: 'center', padding: '32px' }}>
              <div style={{ color: '#e74856', fontFamily: 'monospace', marginBottom: '12px' }}>[AUTHENTICATION REQUIRED]</div>
              <div style={{ color: '#aaa', fontSize: '0.85rem', marginBottom: '20px' }}>Sign in to access your referral dashboard and unique link.</div>
              <button
                className="term-btn-action"
                style={{ borderColor: 'rgba(0,240,255,0.4)', color: '#00F0FF' }}
                onClick={() => navigate('/auth?mode=signup')}
              >
                &gt; AUTHENTICATE()
              </button>
            </div>
          ) : loading ? (
            <div style={{ textAlign: 'center', color: '#555', padding: '40px', fontFamily: 'monospace' }}>
              Loading referral data...
            </div>
          ) : referralInfo && (
            <>
              {/* Referral Link Card */}
              <div className="term-md-card" style={{ marginBottom: '24px', borderColor: 'rgba(0,255,102,0.25)' }}>
                <div style={{ color: '#00FF66', fontWeight: 'bold', padding: '12px 16px', borderBottom: '1px solid rgba(0,255,102,0.1)', fontFamily: 'monospace', fontSize: '0.85rem' }}>
                  [YOUR REFERRAL CREDENTIALS]
                </div>
                <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div>
                    <div style={{ color: '#555', fontSize: '0.75rem', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '6px' }}>Referral Code</div>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <code style={{ background: 'rgba(255,255,255,0.04)', padding: '8px 12px', borderRadius: '6px', color: '#00FF66', fontFamily: 'monospace', fontSize: '1rem', letterSpacing: '2px', border: '1px solid rgba(0,255,102,0.2)' }}>
                        {referralInfo.referral_code}
                      </code>
                      <button
                        onClick={copyCode}
                        className="term-btn-action"
                        style={{ fontSize: '0.8rem', padding: '8px 14px', borderColor: 'rgba(0,255,102,0.3)', color: '#00FF66' }}
                      >
                        {copiedCode ? '✓ COPIED' : 'COPY CODE'}
                      </button>
                    </div>
                  </div>
                  <div>
                    <div style={{ color: '#555', fontSize: '0.75rem', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '6px' }}>Referral Link</div>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                      <code style={{ background: 'rgba(255,255,255,0.03)', padding: '8px 12px', borderRadius: '6px', color: '#aaa', fontFamily: 'monospace', fontSize: '0.82rem', border: '1px solid rgba(255,255,255,0.06)', wordBreak: 'break-all', flex: 1 }}>
                        {referralInfo.referral_url}
                      </code>
                      <button
                        onClick={copyUrl}
                        className="term-btn-action"
                        style={{ fontSize: '0.8rem', padding: '8px 14px', borderColor: 'rgba(0,255,102,0.3)', color: '#00FF66', whiteSpace: 'nowrap' }}
                      >
                        {copied ? '✓ COPIED' : 'COPY LINK'}
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Stats */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '24px' }}>
                {[
                  { label: 'Total Referrals', value: referralInfo.referee_count, color: '#00F0FF' },
                  { label: 'Plans with Discount', value: Object.keys(referralInfo.discounts || {}).length, color: '#ec4899' },
                  { label: 'Total Discount %', value: `${Math.min(totalDiscount, 100).toFixed(0)}%`, color: '#00FF66' },
                ].map(({ label, value, color }) => (
                  <div key={label} className="term-md-card" style={{ textAlign: 'center', padding: '20px 12px' }}>
                    <div style={{ color, fontSize: '1.8rem', fontWeight: 'bold', fontFamily: 'monospace' }}>{value}</div>
                    <div style={{ color: '#555', fontSize: '0.75rem', marginTop: '4px', textTransform: 'uppercase' }}>{label}</div>
                  </div>
                ))}
              </div>

              {/* Discount Breakdown */}
              {Object.keys(referralInfo.discounts || {}).length > 0 && (
                <div className="term-md-card" style={{ marginBottom: '24px' }}>
                  <div style={{ color: '#e8c97a', fontWeight: 'bold', padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.05)', fontFamily: 'monospace', fontSize: '0.85rem' }}>
                    [ACTIVE DISCOUNT BREAKDOWN]
                  </div>
                  <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {Object.entries(referralInfo.discounts).map(([planId, pct]) => {
                      const planMeta = PLAN_LABELS[planId] || { name: planId, color: '#aaa', price_usd: '', price_inr: '' };
                      const barWidth = Math.min(100, pct);
                      return (
                        <div key={planId}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                            <span style={{ color: planMeta.color, fontWeight: 'bold', fontSize: '0.85rem' }}>
                              {planMeta.name}
                              <span style={{ color: '#555', fontWeight: 'normal', marginLeft: '8px', fontSize: '0.75rem' }}>
                                ({planMeta.price_usd} / {planMeta.price_inr})
                              </span>
                            </span>
                            <span style={{ color: '#00FF66', fontFamily: 'monospace', fontWeight: 'bold' }}>
                              {pct >= 100 ? '100% FREE' : `${pct.toFixed(0)}% OFF`}
                            </span>
                          </div>
                          <div style={{ background: 'rgba(255,255,255,0.05)', borderRadius: '4px', height: '6px', overflow: 'hidden' }}>
                            <div style={{ width: `${barWidth}%`, height: '100%', background: pct >= 100 ? '#00FF66' : planMeta.color, borderRadius: '4px', transition: 'width 0.5s ease' }} />
                          </div>
                          <div style={{ color: '#555', fontSize: '0.72rem', marginTop: '4px', fontFamily: 'monospace' }}>
                            {Math.round(pct / 2)} referee purchase{Math.round(pct / 2) !== 1 ? 's' : ''} on this plan
                            {pct < 100 && ` · ${Math.ceil((100 - pct) / 2)} more to make it FREE`}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Referred by */}
              {referralInfo.referred_by && (
                <div className="term-md-card" style={{ marginBottom: '24px', borderColor: 'rgba(255,255,255,0.05)' }}>
                  <div style={{ padding: '12px 16px', color: '#555', fontSize: '0.82rem', fontFamily: 'monospace' }}>
                    [INFO] You were referred by <span style={{ color: '#aaa' }}>{referralInfo.referred_by.display_name}</span> ({referralInfo.referred_by.email_hint})
                  </div>
                </div>
              )}

              {/* Leaderboard */}
              {leaderboard.length > 0 && (
                <div className="term-md-card" style={{ marginBottom: '24px' }}>
                  <div style={{ color: '#00F0FF', fontWeight: 'bold', padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.05)', fontFamily: 'monospace', fontSize: '0.85rem' }}>
                    [TOP REFERRERS LEADERBOARD]
                  </div>
                  <div style={{ padding: '4px 0' }}>
                    {leaderboard.map((entry) => (
                      <div
                        key={entry.rank}
                        style={{
                          display: 'flex', alignItems: 'center', gap: '12px',
                          padding: '10px 16px',
                          borderBottom: '1px solid rgba(255,255,255,0.03)',
                          background: entry.is_me ? 'rgba(0,255,102,0.04)' : 'transparent'
                        }}
                      >
                        <div style={{ color: entry.rank <= 3 ? ['#FFD700','#C0C0C0','#CD7F32'][entry.rank - 1] : '#555', fontFamily: 'monospace', fontWeight: 'bold', minWidth: '28px', fontSize: '0.9rem' }}>
                          #{entry.rank}
                        </div>
                        <div style={{ color: entry.is_me ? '#00FF66' : '#aaa', flex: 1, fontSize: '0.85rem' }}>
                          {entry.name}{entry.is_me && ' (you)'}
                        </div>
                        <div style={{ color: '#00F0FF', fontFamily: 'monospace', fontSize: '0.85rem' }}>
                          {entry.referrals} referrals
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {/* Footer note */}
          <div style={{ color: '#333', fontSize: '0.72rem', textAlign: 'center', marginTop: '16px', fontFamily: 'monospace', lineHeight: '1.6' }}>
            [SYSTEM NOTE] Discounts apply to the monthly base price at checkout time. Discounts are per-plan and cannot be transferred between plans.
            The referral system is monitored for abuse. Discount is capped at 100% per plan.
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReferralPage;
