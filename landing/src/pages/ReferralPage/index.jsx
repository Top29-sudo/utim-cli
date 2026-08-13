import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { getApiUrl } from '../../lib/api';
import ScrollytellingHeaderNav from '../../components/ScrollytellingHeaderNav';
import ScrollytellingFooter from '../../components/ScrollytellingFooter';
import SEOHead from '../../components/SEOHead';
import { Gift, Copy, Check, Users, Award, TrendingUp, Sparkles, ArrowRight } from 'lucide-react';
import '../../components/ScrollytellingMain.css';

const PLAN_LABELS = {
  hobby: { name: 'Hobby Plan', price_usd: '$7', price_inr: '₹700' },
  pro:   { name: 'Pro Plan', price_usd: '$25', price_inr: '₹2,500' },
  max:   { name: 'Max Plan', price_usd: '$55', price_inr: '₹5,500' },
  ultimate: { name: 'Ultimate Plan', price_usd: '$110', price_inr: '₹11,000' },
};

export default function ReferralPage() {
  const { user, getToken } = useAuth();
  const navigate = useNavigate();

  const [referralInfo, setReferralInfo] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading] = useState(true);
  const [copiedUrl, setCopiedUrl] = useState(false);
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
    <div className="st-page-root">
      <SEOHead
        title="Referral Program — Earn Free UTIM Access"
        description="Share UTIM with developers and earn 2% perpetual discount per referral, stacking up to 100% free compute access."
        canonical="https://utim.dev/referral"
      />
      
      <ScrollytellingHeaderNav />

      <div style={{ padding: '60px 24px 100px 24px', maxWidth: 1040, margin: '0 auto' }}>
        
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <div className="st-hero-badge" style={{ display: 'inline-flex', marginBottom: 12 }}>
            <Gift size={14} /> REFERRAL REWARDS PROGRAM
          </div>
          <h1 style={{ fontSize: 'clamp(2.2rem, 4vw, 3.2rem)', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em', marginBottom: 14 }}>
            Earn Free Compute by Sharing UTIM
          </h1>
          <p style={{ fontSize: '1.1rem', color: 'var(--text-muted)', maxWidth: 680, margin: '0 auto', lineHeight: 1.6 }}>
            Every time a referred developer subscribes to a plan, you automatically earn a <strong>2% perpetual discount</strong> on that plan—stacking up to <strong>100% free</strong>.
          </p>
        </div>

        {/* How It Works Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(220px, 100%), 1fr))', gap: 20, marginBottom: 36 }}>
          {[
            { step: '01', title: 'Share Your Link', desc: 'Send your unique referral link or code to colleagues and developers.' },
            { step: '02', title: 'They Subscribe', desc: 'When your referee purchases any compute tier, discount engines trigger.' },
            { step: '03', title: 'You Earn 2% Off', desc: 'You earn 2% perpetual discount per referral on that specific tier.' },
            { step: '04', title: 'Stack to 100% Free', desc: '50 referrals on the same plan = 100% free compute forever.' }
          ].map((item) => (
            <div key={item.step} className="st-doc-card" style={{ padding: 20 }}>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: 6 }}>
                {item.step}
              </div>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>
                {item.title}
              </h3>
              <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                {item.desc}
              </p>
            </div>
          ))}
        </div>

        {!user ? (
          <div className="st-doc-card" style={{ textAlign: 'center', padding: '48px 24px', marginBottom: 36 }}>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: 10 }}>
              Sign In to View Your Referral Dashboard
            </h2>
            <p style={{ fontSize: '0.94rem', color: 'var(--text-muted)', marginBottom: 24 }}>
              Authenticate with your developer account to access your unique referral code and tracking stats.
            </p>
            <Link to="/auth?mode=signup" className="st-nav-primary-btn" style={{ padding: '10px 24px', fontSize: 14 }}>
              Sign In / Register →
            </Link>
          </div>
        ) : loading ? (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
            Loading referral stats...
          </div>
        ) : referralInfo && (
          <>
            {/* Credentials Card */}
            <div className="st-doc-card" style={{ marginBottom: 28 }}>
              <h2 className="st-doc-card-title">
                <Gift size={20} /> Your Referral Link & Credentials
              </h2>
              
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(280px, 100%), 1fr))', gap: 20, marginTop: 16 }}>
                {/* Referral Code */}
                <div>
                  <label style={{ display: 'block', fontSize: 12.5, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase' }}>
                    Referral Code
                  </label>
                  <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                    <div style={{ flex: 1, padding: '10px 14px', background: 'var(--bg-cream-alt)', border: '1px solid var(--border-cream)', borderRadius: 8, fontFamily: 'monospace', fontWeight: 800, fontSize: 16, color: 'var(--text-primary)' }}>
                      {referralInfo.referral_code}
                    </div>
                    <button 
                      onClick={copyCode}
                      className="st-btn-secondary"
                      style={{ padding: '10px 16px', borderRadius: 8, fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 6 }}
                    >
                      {copiedCode ? <><Check size={14} color="#059669" /> Copied</> : <><Copy size={14} /> Copy</>}
                    </button>
                  </div>
                </div>

                {/* Referral URL */}
                <div>
                  <label style={{ display: 'block', fontSize: 12.5, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase' }}>
                    Referral URL
                  </label>
                  <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                    <div style={{ flex: 1, padding: '10px 14px', background: 'var(--bg-cream-alt)', border: '1px solid var(--border-cream)', borderRadius: 8, fontFamily: 'monospace', fontSize: 13, color: 'var(--text-body)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {referralInfo.referral_url}
                    </div>
                    <button 
                      onClick={copyUrl}
                      className="st-nav-primary-btn"
                      style={{ padding: '10px 16px', fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 6 }}
                    >
                      {copiedUrl ? <><Check size={14} /> Copied</> : <><Copy size={14} /> Copy</>}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Stats Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(220px, 100%), 1fr))', gap: 20, marginBottom: 28 }}>
              <div className="st-doc-card" style={{ textAlign: 'center', padding: 24 }}>
                <div style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                  {referralInfo.referee_count || 0}
                </div>
                <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginTop: 4 }}>
                  Total Referrals
                </div>
              </div>

              <div className="st-doc-card" style={{ textAlign: 'center', padding: 24 }}>
                <div style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                  {Object.keys(referralInfo.discounts || {}).length}
                </div>
                <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginTop: 4 }}>
                  Discounted Tiers
                </div>
              </div>

              <div className="st-doc-card" style={{ textAlign: 'center', padding: 24 }}>
                <div style={{ fontSize: '2.2rem', fontWeight: 800, color: '#059669' }}>
                  {Math.min(totalDiscount, 100).toFixed(0)}%
                </div>
                <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginTop: 4 }}>
                  Total Discount Power
                </div>
              </div>
            </div>

            {/* Active Discount Breakdown */}
            {Object.keys(referralInfo.discounts || {}).length > 0 && (
              <div className="st-doc-card" style={{ marginBottom: 28 }}>
                <h2 className="st-doc-card-title">
                  <TrendingUp size={20} /> Active Tier Discounts
                </h2>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 14 }}>
                  {Object.entries(referralInfo.discounts).map(([planId, pct]) => {
                    const planMeta = PLAN_LABELS[planId] || { name: planId, price_usd: '' };
                    return (
                      <div key={planId}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                          <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-primary)' }}>
                            {planMeta.name} ({planMeta.price_usd})
                          </span>
                          <span style={{ fontWeight: 800, color: '#059669' }}>
                            {pct >= 100 ? '100% FREE' : `${pct.toFixed(0)}% OFF`}
                          </span>
                        </div>
                        <div style={{ height: 8, background: 'var(--bg-cream-alt)', borderRadius: 4, overflow: 'hidden' }}>
                          <div style={{ width: `${Math.min(100, pct)}%`, height: '100%', background: 'var(--accent-black)', borderRadius: 4 }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Leaderboard */}
            {leaderboard.length > 0 && (
              <div className="st-doc-card">
                <h2 className="st-doc-card-title">
                  <Award size={20} /> Top Referrers Leaderboard
                </h2>
                <table className="st-commands-table" style={{ marginTop: 14 }}>
                  <thead>
                    <tr style={{ background: 'var(--bg-cream-alt)', textAlign: 'left' }}>
                      <th style={{ padding: '10px 14px', width: '15%' }}>Rank</th>
                      <th style={{ padding: '10px 14px' }}>Developer</th>
                      <th style={{ padding: '10px 14px', textAlign: 'right' }}>Total Referrals</th>
                    </tr>
                  </thead>
                  <tbody>
                    {leaderboard.map((entry) => (
                      <tr key={entry.rank} style={{ background: entry.is_me ? 'rgba(16,185,129,0.06)' : 'transparent' }}>
                        <td style={{ fontWeight: 800 }}>#{entry.rank}</td>
                        <td style={{ fontWeight: 600 }}>{entry.name}{entry.is_me && ' (You)'}</td>
                        <td style={{ textAlign: 'right', fontWeight: 800 }}>{entry.referrals}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

      </div>

      <ScrollytellingFooter />
    </div>
  );
}
