import React, { useEffect, useState, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { getApiUrl } from '../../lib/api';
import { useAuth } from '../../context/AuthContext';

const ActivatePage = () => {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const { user, loading, isAuthenticated } = useAuth();

    const [code, setCode] = useState(searchParams.get('code') || '');
    const [status, setStatus] = useState('idle'); // idle | redirecting | authorizing | success | error
    const [errorMsg, setErrorMsg] = useState('');
    const [countdown, setCountdown] = useState(3);
    const redirected = useRef(false);

    // If user lands without a code in the URL, let them type it
    const [manualCode, setManualCode] = useState('');

    const effectiveCode = code || manualCode.toUpperCase().replace(/[^A-Z0-9-]/g, '');

    // Auto-redirect unauthenticated users to the sign-in page,
    // preserving the device code so they return here automatically.
    useEffect(() => {
        if (loading) return;
        if (isAuthenticated) return;
        if (redirected.current) return;

        // Only auto-redirect if we have a code (CLI-initiated flow)
        if (!effectiveCode || effectiveCode.length < 9) return;

        redirected.current = true;
        setStatus('redirecting');

        // Countdown then redirect
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [loading, isAuthenticated, effectiveCode]);

    const handleAuthorize = async () => {
        if (!effectiveCode || effectiveCode.length < 9) {
            setErrorMsg('Please enter a valid 8-character code (e.g. DFRG-TYHJ).');
            return;
        }
        if (!isAuthenticated || !user) {
            // Trigger immediate redirect preserving the code
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

    const styles = {
        wrapper: {
            minHeight: '100vh',
            background: '#0d1117',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
            padding: '20px',
        },
        card: {
            background: '#161b22',
            border: '1px solid #30363d',
            borderRadius: '12px',
            padding: '48px 40px',
            maxWidth: '480px',
            width: '100%',
            textAlign: 'center',
            boxShadow: '0 16px 48px rgba(0,0,0,0.6)',
        },
        termTag: {
            color: '#3fb950',
            fontSize: '0.75rem',
            letterSpacing: '0.1em',
            marginBottom: '16px',
            display: 'block',
        },
        title: {
            color: '#e6edf3',
            fontSize: '1.4rem',
            fontWeight: 'bold',
            marginBottom: '8px',
        },
        subtitle: {
            color: '#8b949e',
            fontSize: '0.85rem',
            lineHeight: '1.6',
            marginBottom: '32px',
        },
        codeDisplay: {
            background: '#0d1117',
            border: '2px solid #f9e2af',
            borderRadius: '8px',
            padding: '16px 24px',
            fontSize: '1.8rem',
            fontWeight: 'bold',
            letterSpacing: '0.15em',
            color: '#f9e2af',
            marginBottom: '24px',
            display: 'inline-block',
        },
        input: {
            width: '100%',
            background: '#0d1117',
            border: '1px solid #30363d',
            borderRadius: '8px',
            padding: '12px 16px',
            fontSize: '1.2rem',
            fontWeight: 'bold',
            letterSpacing: '0.15em',
            color: '#f9e2af',
            textAlign: 'center',
            textTransform: 'uppercase',
            marginBottom: '24px',
            outline: 'none',
            boxSizing: 'border-box',
        },
        btn: {
            width: '100%',
            padding: '14px',
            background: status === 'authorizing' ? '#238636aa' : '#238636',
            border: 'none',
            borderRadius: '8px',
            color: '#fff',
            fontSize: '1rem',
            fontWeight: 'bold',
            cursor: status === 'authorizing' ? 'not-allowed' : 'pointer',
            transition: 'background 0.2s',
            fontFamily: 'inherit',
            letterSpacing: '0.05em',
        },
        signInNote: {
            color: '#8b949e',
            fontSize: '0.8rem',
            marginTop: '16px',
        },
        signInLink: {
            color: '#58a6ff',
            cursor: 'pointer',
            textDecoration: 'underline',
        },
        error: {
            background: 'rgba(248,81,73,0.1)',
            border: '1px solid rgba(248,81,73,0.4)',
            borderRadius: '6px',
            color: '#f85149',
            padding: '10px 14px',
            fontSize: '0.85rem',
            marginBottom: '16px',
            textAlign: 'left',
        },
        success: {
            textAlign: 'center',
        },
        successIcon: {
            color: '#3fb950',
            fontSize: '3rem',
            marginBottom: '16px',
        },
        successTitle: {
            color: '#3fb950',
            fontSize: '1.4rem',
            fontWeight: 'bold',
            marginBottom: '8px',
        },
        successSub: {
            color: '#8b949e',
            fontSize: '0.9rem',
            lineHeight: '1.6',
        },
    };

    if (loading) {
        return (
            <div style={styles.wrapper}>
                <div style={styles.card}>
                    <span style={styles.termTag}>[UTIM DEVICE AUTHORIZATION]</span>
                    <div style={{ color: '#8b949e', display: 'flex', alignItems: 'center', gap: '12px', justifyContent: 'center' }}>
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#58a6ff" strokeWidth="2.5" strokeLinecap="round">
                            <line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/>
                            <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/>
                            <line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/>
                            <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/>
                        </svg>
                        Verifying session…
                    </div>
                </div>
            </div>
        );
    }

    // Auto-redirecting unauthenticated users to the sign-in page
    if (status === 'redirecting') {
        return (
            <div style={styles.wrapper}>
                <div style={styles.card}>
                    <span style={styles.termTag}>[UTIM DEVICE AUTHORIZATION]</span>
                    <div style={{ color: '#f9e2af', fontSize: '2rem', marginBottom: '16px' }}>🔐</div>
                    <div style={{ color: '#e6edf3', fontSize: '1.1rem', fontWeight: 'bold', marginBottom: '8px' }}>Sign-In Required</div>
                    <div style={{ color: '#8b949e', fontSize: '0.88rem', lineHeight: '1.7', marginBottom: '24px' }}>
                        You need to be signed in to authorize your terminal.<br />
                        Redirecting you to the sign-in page…
                    </div>
                    <div style={styles.codeDisplay}>{effectiveCode}</div>
                    <div style={{ color: '#58a6ff', fontSize: '0.85rem', marginTop: '12px' }}>
                        Redirecting in <strong>{countdown}</strong>s…
                    </div>
                    <button
                        style={{ ...styles.btn, marginTop: '20px', background: '#238636' }}
                        onClick={() => navigate(`/auth?redirect=/activate?code=${effectiveCode}`)}
                    >
                        Sign In Now →
                    </button>
                </div>
            </div>
        );
    }

    if (status === 'success') {
        return (
            <div style={styles.wrapper}>
                <div style={styles.card}>
                    <div style={styles.success}>
                        <div style={styles.successIcon}>✓</div>
                        <div style={styles.successTitle}>Device Authorized!</div>
                        <div style={styles.successSub}>
                            Your terminal is now signed in.<br />
                            You can close this tab and return to UTIM.
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div style={styles.wrapper}>
            <div style={styles.card}>
                <span style={styles.termTag}>[UTIM DEVICE AUTHORIZATION]</span>
                <div style={styles.title}># Authorize UTIM CLI</div>
                <div style={styles.subtitle}>
                    Sign in to authorize your terminal device.<br />
                    Your API key is never shown or stored in your browser.
                </div>

                {/* Code display or input */}
                {effectiveCode && effectiveCode.length === 9 ? (
                    <div style={styles.codeDisplay}>{effectiveCode}</div>
                ) : (
                    <input
                        style={styles.input}
                        type="text"
                        placeholder="XXXX-XXXX"
                        maxLength={9}
                        value={manualCode}
                        onChange={(e) => setManualCode(e.target.value)}
                    />
                )}

                {/* Auth status */}
                {!isAuthenticated && (
                    <div style={{ ...styles.signInNote, background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.25)', padding: '10px 14px', borderRadius: '6px', marginBottom: '12px', color: '#f85149', fontSize: '0.83rem' }}>
                        ⚠ You are not signed in.{' '}
                        <span
                            style={styles.signInLink}
                            onClick={() => navigate(`/auth?redirect=/activate?code=${effectiveCode}`)}
                        >
                            Sign in to authorize →
                        </span>
                    </div>
                )}

                {isAuthenticated && (
                    <div style={{ color: '#3fb950', fontSize: '0.8rem', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'center' }}>
                        <span>✓</span> Signed in as <strong>{user?.email}</strong>
                    </div>
                )}

                {/* Error */}
                {errorMsg && <div style={styles.error}>{errorMsg}</div>}

                {/* Authorize button */}
                <button
                    style={styles.btn}
                    onClick={handleAuthorize}
                    disabled={status === 'authorizing'}
                >
                    {status === 'authorizing' ? '  Authorizing…' : '> Authorize UTIM CLI'}
                </button>
            </div>
        </div>
    );
};

export default ActivatePage;
