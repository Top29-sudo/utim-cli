import React, { useEffect, useState } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import './AuthCallback.css';

const AuthCallback = () => {
    const { user, userProfile, loading, getToken } = useAuth();
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const [token, setToken] = useState(null);
    const [countdown, setCountdown] = useState(5);
    const [autoRedirecting, setAutoRedirecting] = useState(false);

    // Get the redirect URL for UTIM CLI
    const redirectUrl = searchParams.get('redirect');
    const isCliHandshakeFlow = !!redirectUrl;

    // Get the token when user is authenticated
    useEffect(() => {
        const fetchToken = async () => {
            if (user && !loading) {
                const idToken = await getToken();
                setToken(idToken);
            }
        };
        fetchToken();
    }, [user, loading, getToken]);

    // Auto-redirect countdown for CLI handshake flow (only if email is verified or Google user)
    const isVerified = user?.emailVerified || user?.providerData?.[0]?.providerId === 'google.com';

    useEffect(() => {
        if (isCliHandshakeFlow && token && countdown > 0 && isVerified) {
            setAutoRedirecting(true);
            const timer = setTimeout(() => {
                setCountdown(prev => prev - 1);
            }, 1000);
            return () => clearTimeout(timer);
        } else if (isCliHandshakeFlow && token && countdown === 0 && isVerified) {
            // Trigger redirect
            handleReturnToCLI();
        }
    }, [isCliHandshakeFlow, token, countdown, isVerified]);

    // If not authenticated, redirect to auth page
    useEffect(() => {
        if (!loading && !user) {
            navigate('/auth' + (redirectUrl ? `?callback=${encodeURIComponent(redirectUrl)}` : ''));
        }
    }, [loading, user, navigate, redirectUrl]);

    const handleReturnToCLI = () => {
        if (token && redirectUrl) {
            // Build the callback URL with the token
            const displayName = userProfile?.displayName || user.displayName || '';
            const callbackWithToken = `${redirectUrl}?token=${encodeURIComponent(token)}&email=${encodeURIComponent(user.email)}&uid=${encodeURIComponent(user.uid)}&name=${encodeURIComponent(displayName)}`;
            window.location.href = callbackWithToken;
        }
    };

    // Get initials for avatar
    const getInitials = () => {
        if (!user) return '?';
        const name = userProfile?.displayName || user.displayName || user.email;
        if (!name) return '?';
        const parts = name.split(' ');
        if (parts.length >= 2) {
            return parts[0][0] + parts[1][0];
        }
        return name[0];
    };

    if (loading) {
        return (
            <div className="term-wrapper" style={{ padding: '0', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <div className="term-window" style={{ maxWidth: '960px', width: '100%' }}>
                    <div className="term-titlebar">
                      <div className="term-tab" onClick={() => navigate('/')}>
                        <span className="term-tab-icon" style={{color: '#3b78ff'}}>&gt;_</span>
                        <span className="term-tab-title">Home</span>
                      </div>
                      <div className="term-tab active">
                        <span className="term-tab-icon" style={{color: '#e5ff00'}}>●</span>
                        <span className="term-tab-title">Authenticating...</span>
                      </div>
                    </div>
                    <div className="term-content" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '60px 32px', minHeight: '300px' }}>
                        <div className="term-md-card" style={{ maxWidth: '440px', width: '100%', margin: '20px auto', padding: '32px', border: '1px solid rgba(255, 255, 255, 0.07)', borderRadius: '12px', background: '#0a0a0a', textAlign: 'center' }}>
                            <div className="callback-icon loading">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <circle cx="12" cy="12" r="10" />
                                </svg>
                            </div>
                            <h1 className="callback-title" style={{ fontSize: '1.4rem', color: '#fff', marginBottom: '8px' }}>Authenticating...</h1>
                            <p className="callback-subtitle" style={{ color: '#555', fontSize: '0.88rem' }}>Establishing secure handshake with CLI...</p>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    if (!user) {
        return null; // Will redirect via useEffect
    }

    return (
        <div className="term-wrapper" style={{ padding: '0', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div className="term-window" style={{ maxWidth: '960px', width: '100%' }}>
                <div className="term-titlebar">
                  <div className="term-tab" onClick={() => navigate('/')}>
                    <span className="term-tab-icon" style={{color: '#3b78ff'}}>&gt;_</span>
                    <span className="term-tab-title">Home</span>
                  </div>
                  <div className="term-tab active">
                    <span className="term-tab-icon" style={{color: '#27c93f'}}>✓</span>
                    <span className="term-tab-title">Handshake</span>
                  </div>
                  <div className="term-window-controls">
                    <div className="term-ctrl">_</div>
                    <div className="term-ctrl">□</div>
                    <div className="term-ctrl close" onClick={() => navigate('/')}>×</div>
                  </div>
                </div>

                <div className="term-content" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 'auto', padding: '32px' }}>
                    <div className="term-md-card" style={{ maxWidth: '460px', width: '100%', margin: '20px auto', padding: '32px', border: '1px solid rgba(255, 255, 255, 0.07)', borderRadius: '12px', background: '#0a0a0a', textAlign: 'center' }}>
                        <div className="term-md-tag" style={{ color: '#27c93f', marginBottom: '14px', fontSize: '0.8rem', fontWeight: 'bold' }}>[SECURE LINK ESTABLISHED]</div>
                        
                        <div className="callback-icon">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                                <path d="M20 6L9 17l-5-5" />
                            </svg>
                        </div>

                        <h2 className="term-md-title" style={{ fontSize: '1.4rem', marginBottom: '8px', color: '#fff' }}>Handshake Successful!</h2>
                        <p style={{ color: '#555', fontSize: '0.88rem', marginBottom: '24px', lineHeight: '1.5' }}>
                            {isCliHandshakeFlow
                                ? "Handshake complete. You can now return to your terminal to continue using UTIM."
                                : "Welcome to UTIM! Your developer identity has been verified."}
                        </p>

                        {!isVerified && (
                            <div style={{ background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.3)', color: '#fbbf24', padding: '14px', borderRadius: '8px', marginBottom: '20px', fontSize: '0.85rem', textAlign: 'left' }}>
                                <div style={{ fontWeight: 'bold', marginBottom: '4px', fontSize: '0.9rem' }}>
                                    ✉️ Email Verification Required
                                </div>
                                Please check your inbox ({user.email}) and click the verification link before connecting UTIM CLI.
                            </div>
                        )}

                        <div className="callback-user" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)', padding: '12px', borderRadius: '8px' }}>
                            <div className="callback-user-avatar">
                                {user.photoURL ? (
                                    <img src={user.photoURL} alt="" />
                                ) : (
                                    getInitials()
                                )}
                            </div>
                            <div className="callback-user-info">
                                <div className="callback-user-name">
                                    {userProfile?.displayName || user.displayName || 'UTIM User'}
                                </div>
                                <div className="callback-user-email">{user.email}</div>
                            </div>
                        </div>

                        <div className="callback-actions" style={{ marginTop: '24px' }}>
                            {isCliHandshakeFlow ? (
                                <>
                                    <button onClick={handleReturnToCLI} className="callback-btn callback-btn-primary" style={{ background: '#27c93f', border: 'none', color: '#000' }}>
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                                            <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
                                            <line x1="12" y1="22.08" x2="12" y2="12" />
                                        </svg>
                                        Return to CLI
                                    </button>

                                    <Link to="/profile" className="callback-btn callback-btn-secondary" style={{ border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '6px' }}>
                                        View Profile
                                    </Link>

                                    {autoRedirecting && countdown > 0 && (
                                        <p className="callback-countdown" style={{ fontSize: '0.8rem', color: '#555', marginTop: '12px' }}>
                                            Automatically returning in <span style={{ color: '#27c93f', fontWeight: 'bold' }}>{countdown}</span> seconds...
                                        </p>
                                    )}
                                </>
                            ) : (
                                <>
                                    <Link to="/profile" className="callback-btn callback-btn-primary" style={{ background: '#27c93f', border: 'none', color: '#000' }}>
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                                            <circle cx="12" cy="7" r="4" />
                                        </svg>
                                        View Profile
                                    </Link>

                                    <Link to="/" className="callback-btn callback-btn-secondary" style={{ border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '6px' }}>
                                        Go to Home
                                    </Link>
                                </>
                            )}
                        </div>

                        {isCliHandshakeFlow && (
                            <div className="callback-note" style={{ fontSize: '0.8rem', color: '#555', background: 'rgba(39, 201, 63, 0.05)', border: '1px solid rgba(39, 201, 63, 0.1)', marginTop: '20px', borderRadius: '8px' }}>
                                <strong>Trouble returning?</strong> If your terminal doesn't open, copy/paste the redirect link or click the action button.
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default AuthCallback;
