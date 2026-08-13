import React, { useEffect, useState } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import ScrollytellingHeaderNav from '../../components/ScrollytellingHeaderNav';
import ScrollytellingFooter from '../../components/ScrollytellingFooter';
import SEOHead from '../../components/SEOHead';
import { Check, ShieldCheck, Terminal, User, ArrowRight, RefreshCw } from 'lucide-react';
import '../../components/ScrollytellingMain.css';

export default function AuthCallback() {
  const { user, userProfile, loading, getToken } = useAuth();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [token, setToken] = useState(null);
  const [countdown, setCountdown] = useState(4);
  const [autoRedirecting, setAutoRedirecting] = useState(false);

  const redirectUrl = searchParams.get('redirect');
  const isCliHandshakeFlow = !!redirectUrl;

  useEffect(() => {
    const fetchToken = async () => {
      if (user && !loading) {
        const idToken = await getToken();
        setToken(idToken);
      }
    };
    fetchToken();
  }, [user, loading, getToken]);

  const isVerified = user?.emailVerified || user?.providerData?.[0]?.providerId === 'google.com';

  useEffect(() => {
    if (isCliHandshakeFlow && token && countdown > 0 && isVerified) {
      setAutoRedirecting(true);
      const timer = setTimeout(() => {
        setCountdown(prev => prev - 1);
      }, 1000);
      return () => clearTimeout(timer);
    } else if (isCliHandshakeFlow && token && countdown === 0 && isVerified) {
      handleReturnToCLI();
    }
  }, [isCliHandshakeFlow, token, countdown, isVerified]);

  useEffect(() => {
    if (!loading && !user) {
      navigate('/auth' + (redirectUrl ? `?callback=${encodeURIComponent(redirectUrl)}` : ''));
    }
  }, [loading, user, navigate, redirectUrl]);

  const handleReturnToCLI = () => {
    if (token && redirectUrl) {
      const displayName = userProfile?.displayName || user.displayName || '';
      const callbackWithToken = `${redirectUrl}?token=${encodeURIComponent(token)}&email=${encodeURIComponent(user.email)}&uid=${encodeURIComponent(user.uid)}&name=${encodeURIComponent(displayName)}`;
      window.location.href = callbackWithToken;
    }
  };

  if (loading || !user) {
    return (
      <div className="st-page-root">
        <ScrollytellingHeaderNav />
        <div style={{ minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ color: 'var(--text-muted)', fontSize: 15, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 10 }}>
            <RefreshCw size={18} className="st-spin" />
            <span>Establishing secure authentication handshake...</span>
          </div>
        </div>
        <ScrollytellingFooter />
      </div>
    );
  }

  return (
    <div className="st-page-root">
      <SEOHead
        title="Secure Handshake — UTIM AI"
        description="Authenticating developer identity and pairing local terminal session."
        canonical="https://utim.dev/auth/callback"
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
            <ShieldCheck size={14} /> SECURE HANDSHAKE VERIFIED
          </div>

          <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(16,185,129,0.1)', color: '#059669', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px auto' }}>
            <Check size={32} />
          </div>

          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em', marginBottom: 8 }}>
            Handshake Successful!
          </h1>
          
          <p style={{ fontSize: '0.94rem', color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: 24 }}>
            {isCliHandshakeFlow
              ? "Your developer identity is verified. You can now return to your local terminal session."
              : "Welcome to UTIM! Your developer session is active."}
          </p>

          <div style={{ background: 'var(--bg-cream-alt)', border: '1px solid var(--border-cream)', borderRadius: 10, padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 14, textAlign: 'left', marginBottom: 24 }}>
            <div style={{ width: 44, height: 44, borderRadius: '50%', background: 'var(--accent-black)', color: '#FFFFFF', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 16 }}>
              {user.displayName ? user.displayName.charAt(0).toUpperCase() : user.email.charAt(0).toUpperCase()}
            </div>
            <div>
              <div style={{ fontWeight: 800, color: 'var(--text-primary)', fontSize: 14.5 }}>
                {user.displayName || userProfile?.displayName || 'UTIM Developer'}
              </div>
              <div style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>
                {user.email}
              </div>
            </div>
          </div>

          {isCliHandshakeFlow ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <button 
                onClick={handleReturnToCLI}
                className="st-nav-primary-btn"
                style={{ width: '100%', padding: '12px', fontSize: 14.5, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
              >
                <Terminal size={16} />
                <span>Return to Terminal</span>
              </button>

              <Link to="/profile" className="st-btn-secondary" style={{ width: '100%', padding: '10px', borderRadius: 8, fontSize: 13.5 }}>
                View Dashboard
              </Link>

              {autoRedirecting && countdown > 0 && (
                <p style={{ fontSize: 12.5, color: 'var(--text-muted)', marginTop: 8 }}>
                  Automatically returning to CLI in <strong>{countdown}s</strong>...
                </p>
              )}
            </div>
          ) : (
            <div style={{ display: 'flex', gap: 12 }}>
              <Link to="/profile" className="st-nav-primary-btn" style={{ flex: 1, padding: '10px', fontSize: 14 }}>
                View Dashboard
              </Link>
              <Link to="/" className="st-btn-secondary" style={{ flex: 1, padding: '10px', borderRadius: 8, fontSize: 14 }}>
                Go to Home
              </Link>
            </div>
          )}
        </div>
      </div>

      <ScrollytellingFooter />
    </div>
  );
}
