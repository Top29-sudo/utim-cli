import React, { useEffect, useState, useRef } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { getApiUrl } from '../../lib/api';
import { useAuth } from '../../context/AuthContext';
import ScrollytellingHeaderNav from '../../components/ScrollytellingHeaderNav';
import ScrollytellingFooter from '../../components/ScrollytellingFooter';
import SEOHead from '../../components/SEOHead';
import { Terminal, ShieldCheck, Check, AlertCircle, Sparkles, ArrowRight } from 'lucide-react';
import '../../components/ScrollytellingMain.css';

export default function ActivatePage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user, loading, isAuthenticated } = useAuth();

  const [code, setCode] = useState(searchParams.get('code') || '');
  const [status, setStatus] = useState('idle'); // idle | redirecting | authorizing | success | error
  const [errorMsg, setErrorMsg] = useState('');
  const [countdown, setCountdown] = useState(3);
  const redirected = useRef(false);
  const [manualCode, setManualCode] = useState('');

  const effectiveCode = code || manualCode.toUpperCase().replace(/[^A-Z0-9-]/g, '');

  useEffect(() => {
    if (loading) return;
    if (isAuthenticated) return;
    if (redirected.current) return;

    if (!effectiveCode || effectiveCode.length < 9) return;

    redirected.current = true;
    setStatus('redirecting');

    let count = 3;
    setCountdown(count);
    const interval = setInterval(() => {
      count -= 1;
      setCountdown(count);
      if (count <= 0) {
        clearInterval(interval);
        navigate(`/auth?redirect=/activate?code=${effectiveCode}`);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [loading, isAuthenticated, effectiveCode, navigate]);

  const handleAuthorize = async () => {
    if (!effectiveCode || effectiveCode.length < 9) {
      setErrorMsg('Please enter a valid 8-character code (e.g. DFRG-TYHJ).');
      return;
    }
    if (!isAuthenticated || !user) {
      navigate(`/auth?redirect=/activate?code=${effectiveCode}`);
      return;
    }

    setStatus('authorizing');
    setErrorMsg('');
    try {
      const idToken = await user.getIdToken();
      const apiUrl = getApiUrl() || 'https://api.utim.dev';
      const resp = await fetch(`${apiUrl}/auth/device/authorize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_code: effectiveCode, id_token: idToken }),
      });
      const data = await resp.json();
      if (resp.ok && data.success) {
        setStatus('success');
      } else {
        setStatus('error');
        setErrorMsg(data.detail || 'Authorization failed. The code may be expired or already used.');
      }
    } catch (err) {
      setStatus('error');
      setErrorMsg(`Network error: ${err.message}`);
    }
  };

  return (
    <div className="st-page-root">
      <SEOHead
        title="Device Authorization — UTIM AI CLI"
        description="Pair and authorize your local workstation terminal with your UTIM developer account."
        canonical="https://utim.dev/activate"
      />
      
      <ScrollytellingHeaderNav />

      <div style={{ padding: '70px 24px 100px 24px', display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 'calc(100vh - 180px)' }}>
        <div style={{
          background: '#FFFFFF',
          position: 'relative',
          zIndex: 1,
          border: '1px solid var(--border-cream)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-lg)',
          maxWidth: 480,
          width: '100%',
          padding: '44px 36px',
          textAlign: 'center'
        }}>
          <div className="st-hero-badge" style={{ display: 'inline-flex', marginBottom: 14 }}>
            <Terminal size={14} /> CLI DEVICE PAIRING
          </div>

          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em', marginBottom: 8 }}>
            Authorize UTIM Terminal
          </h1>
          
          <p style={{ fontSize: '0.92rem', color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: 28 }}>
            Confirm your 8-character device verification code to pair your local workstation session securely.
          </p>

          {/* Success State */}
          {status === 'success' ? (
            <div style={{ padding: '24px 0' }}>
              <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(16,185,129,0.1)', color: '#059669', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px auto' }}>
                <Check size={32} />
              </div>
              <h2 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: 8 }}>
                Terminal Device Authorized!
              </h2>
              <p style={{ fontSize: '0.92rem', color: 'var(--text-body)', lineHeight: 1.6, marginBottom: 24 }}>
                Your local CLI session is now successfully paired with your UTIM subscription quota. You can close this browser tab and return to your terminal.
              </p>
              <Link to="/profile" className="st-nav-primary-btn" style={{ padding: '10px 22px', fontSize: 14 }}>
                Go to Developer Dashboard
              </Link>
            </div>
          ) : status === 'redirecting' ? (
            <div>
              <p style={{ fontSize: '0.92rem', color: 'var(--text-body)', marginBottom: 16 }}>
                Sign-in required to authorize this terminal. Redirecting in <strong>{countdown}s</strong>...
              </p>
              <div style={{ 
                background: 'var(--bg-cream-alt)', 
                border: '2px solid var(--border-cream)', 
                borderRadius: 10, 
                padding: '14px 20px', 
                fontSize: '1.8rem', 
                fontWeight: 800, 
                letterSpacing: '0.2em', 
                color: 'var(--text-primary)',
                fontFamily: 'monospace',
                marginBottom: 20
              }}>
                {effectiveCode}
              </div>
              <button 
                onClick={() => navigate(`/auth?redirect=/activate?code=${effectiveCode}`)}
                className="st-nav-primary-btn"
                style={{ width: '100%', padding: '12px' }}
              >
                Sign In Now →
              </button>
            </div>
          ) : (
            <div>
              {/* Code Display or Input */}
              {effectiveCode && effectiveCode.length === 9 ? (
                <div style={{ 
                  background: 'var(--bg-cream-alt)', 
                  border: '2px solid var(--border-cream)', 
                  borderRadius: 10, 
                  padding: '14px 20px', 
                  fontSize: '1.8rem', 
                  fontWeight: 800, 
                  letterSpacing: '0.2em', 
                  color: 'var(--text-primary)',
                  fontFamily: 'monospace',
                  marginBottom: 20
                }}>
                  {effectiveCode}
                </div>
              ) : (
                <input
                  type="text"
                  placeholder="XXXX-XXXX"
                  maxLength={9}
                  value={manualCode}
                  onChange={(e) => setManualCode(e.target.value)}
                  style={{ 
                    width: '100%', 
                    padding: '12px', 
                    borderRadius: 10, 
                    border: '1px solid var(--border-cream)', 
                    background: 'var(--bg-cream-alt)', 
                    textAlign: 'center', 
                    fontSize: '1.4rem', 
                    fontWeight: 800, 
                    letterSpacing: '0.15em', 
                    color: 'var(--text-primary)',
                    fontFamily: 'monospace',
                    textTransform: 'uppercase',
                    marginBottom: 20,
                    outline: 'none'
                  }}
                />
              )}

              {/* User Sign-In Notice */}
              {isAuthenticated ? (
                <div style={{ color: 'var(--text-body)', fontSize: 13, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'center' }}>
                  <Check size={16} color="#059669" />
                  <span>Signed in as <strong>{user.email}</strong></span>
                </div>
              ) : (
                <div style={{ background: 'var(--bg-cream-alt)', border: '1px solid var(--border-cream)', padding: '10px 14px', borderRadius: 8, fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
                  You must sign in before pairing. <Link to={`/auth?redirect=/activate?code=${effectiveCode}`} style={{ color: 'var(--text-primary)', fontWeight: 700 }}>Sign in here →</Link>
                </div>
              )}

              {/* Error Message */}
              {errorMsg && (
                <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', color: '#DC2626', padding: '10px 14px', borderRadius: 8, fontSize: 13, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <AlertCircle size={16} />
                  <span>{errorMsg}</span>
                </div>
              )}

              {/* Authorize Button */}
              <button
                onClick={handleAuthorize}
                disabled={status === 'authorizing'}
                className="st-nav-primary-btn"
                style={{ width: '100%', padding: '12px', fontSize: 14.5, fontWeight: 700 }}
              >
                {status === 'authorizing' ? 'Authorizing Local Terminal...' : 'Authorize UTIM CLI'}
              </button>
            </div>
          )}
        </div>
      </div>

      <ScrollytellingFooter />
    </div>
  );
}
