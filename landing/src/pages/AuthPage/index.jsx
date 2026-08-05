import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { getApiUrl } from '../../lib/api';
import { motion, AnimatePresence } from 'framer-motion';
import '../../components/PowershellUI/PowershellUI.css';
import './AuthPage.css';

const AuthPage = () => {
    const [searchParams] = useSearchParams();
    const [mode, setMode] = useState(() => searchParams.get('mode') === 'signup' ? 'signup' : 'signin');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [displayName, setDisplayName] = useState('');
    const [referralCode, setReferralCode] = useState(() => searchParams.get('ref') || '');
    const [formLoading, setFormLoading] = useState(false);
    const [error, setError] = useState('');

    const [verificationSent, setVerificationSent] = useState(false);
    const [resendStatus, setResendStatus] = useState('');
    const [otpSent, setOtpSent] = useState(false);
    const [otpCode, setOtpCode] = useState('');
    const [otpMessage, setOtpMessage] = useState('');
    const [otpVerified, setOtpVerified] = useState(false);
    const [resendOtpLoading, setResendOtpLoading] = useState(false);
    const [newPassword, setNewPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    // Login-page OTP recovery (for unverified email accounts)
    const [loginNeedsOtp, setLoginNeedsOtp] = useState(false);
    const [loginOtpCode, setLoginOtpCode] = useState('');
    const [loginOtpVerifying, setLoginOtpVerifying] = useState(false);

    const { login, register, sendOTP, verifyOTP, sendResetOTP, resetPasswordWithOTP, resendVerificationEmail, loginWithGoogle, isAuthenticated, isEmailVerified, user, loading: authLoading, error: authError, getToken } = useAuth();
    const navigate = useNavigate();

    // Get callback URL from query params (for CLI client handshake redirect)
    const callbackUrl = searchParams.get('callback');
    // Get redirect URL — used by the device auth flow (/activate page)
    const redirectUrl = searchParams.get('redirect');
    const isCliFlow = !!callbackUrl || !!redirectUrl;

    // Redirect as soon as the user is authenticated — isEmailVerified is always true
    // for logged-in users since our backend OTP system is the verification gate.
    useEffect(() => {
        if (authLoading) return;

        if (isAuthenticated) {
            if (callbackUrl) {
                navigate(`/auth/callback?redirect=${encodeURIComponent(callbackUrl)}`);
            } else if (redirectUrl) {
                navigate(redirectUrl);
            } else {
                navigate('/profile');
            }
        }
    }, [isAuthenticated, callbackUrl, redirectUrl, navigate, authLoading]);

    // Update error from auth context
    useEffect(() => {
        if (authError) {
            setError(authError);
        }
    }, [authError]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setFormLoading(true);

        const cleanEmail = email.trim().toLowerCase();
        const cleanPassword = password.trim();
        const cleanNewPassword = newPassword.trim();

        const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        if (!emailRegex.test(cleanEmail)) {
            setError('Please enter a valid email address.');
            setFormLoading(false);
            return;
        }

        const disposableDomains = [
            'mailinator.com', 'dispostable.com', '10minutemail.com', 'tempmail.com',
            'trashmail.com', 'fakeinbox.com', 'yopmail.com', 'getairmail.com',
            'guerrillamail.com', 'sharklasers.com', 'throwawaymail.com', 'temp-mail.org',
            'gmx.com', 'test.com', 'example.com', 'asdf.com', 'fake.com', 'foo.com',
            'bar.com', 'domain.com', 'invalid.com', 'email.com', 'temp.com'
        ];
        const domain = cleanEmail.split('@')[1] || '';
        if (disposableDomains.some(d => domain === d || domain.endsWith('.' + d))) {
            setError('Disposable or fake email addresses are not allowed. Please use a valid email address.');
            setFormLoading(false);
            return;
        }

        try {
            if (mode === 'signin') {
                // If we're in OTP recovery mode (loginNeedsOtp), verify the code first
                if (loginNeedsOtp) {
                    if (!loginOtpCode.trim() || loginOtpCode.trim().length !== 6) {
                        setError('Please enter the 6-digit code sent to your email.');
                        setFormLoading(false);
                        return;
                    }
                    setLoginOtpVerifying(true);
                    try {
                        await verifyOTP(cleanEmail, loginOtpCode.trim(), cleanPassword);
                        setOtpVerified(true);
                        setLoginNeedsOtp(false);
                        // Now sign in — email is now verified in Firebase
                        await login(cleanEmail, cleanPassword);
                    } catch (vErr) {
                        setError(vErr.message || 'Invalid or expired verification code.');
                    } finally {
                        setLoginOtpVerifying(false);
                    }
                    setFormLoading(false);
                    return;
                }

                try {
                    await login(cleanEmail, cleanPassword);
                    // Login succeeded — backend will validate OTP verification status.
                    // No client-side emailVerified check needed; our OTP system is the source of truth.
                } catch (loginErr) {
                    const msg = loginErr.message || '';
                    if (msg.toLowerCase().includes('not verified') || msg.toLowerCase().includes('forbidden') || msg.toLowerCase().includes('403')) {
                        // Server-side 403 — account exists but email not yet OTP-verified
                        try { await sendOTP(cleanEmail); } catch (_) {}
                        setLoginNeedsOtp(true);
                        setLoginOtpCode('');
                        setError('');
                        setOtpMessage(`A 6-digit verification code has been sent to ${cleanEmail}. Enter it below to complete sign-in.`);
                    } else if (msg.includes('Incorrect') || msg.includes('Invalid') || msg.includes('wrong-password') || msg.includes('user-not-found') || msg.includes('credential')) {
                        setError('Incorrect email or passphrase. Please double-check your passphrase or click "Forgot Passphrase?" below to reset it.');
                    } else {
                        setError(msg || 'Sign in failed. Please check your credentials.');
                    }
                }
            } else if (mode === 'forgot') {
                // Step 1: Send Password Reset OTP
                if (!otpSent) {
                    try {
                        const res = await sendResetOTP(cleanEmail);
                        setOtpSent(true);
                        setOtpMessage(res.message || `Password reset code sent to ${cleanEmail}. Check your inbox!`);
                    } catch (otpErr) {
                        setError(otpErr.message || 'Failed to send password reset code.');
                    }
                    setFormLoading(false);
                    return;
                }

                // Step 2: Verify OTP & Reset Password
                if (!otpCode.trim() || otpCode.trim().length !== 6) {
                    setError('Please enter the 6-digit OTP code sent to your email.');
                    setFormLoading(false);
                    return;
                }

                if (!cleanNewPassword || cleanNewPassword.length < 6) {
                    setError('New passphrase must be at least 6 characters long.');
                    setFormLoading(false);
                    return;
                }

                try {
                    await resetPasswordWithOTP(cleanEmail, otpCode.trim(), cleanNewPassword);
                    setOtpVerified(true);
                    // Automatically log in user with new password!
                    await login(cleanEmail, cleanNewPassword);
                } catch (resetErr) {
                    setError(resetErr.message || 'Password reset failed. Please try again.');
                    setFormLoading(false);
                    return;
                }
            } else {
                if (!displayName.trim()) {
                    setError('Please enter your name');
                    setFormLoading(false);
                    return;
                }

                // Step 1: Send OTP email if not yet sent
                if (!otpSent) {
                    try {
                        const res = await sendOTP(cleanEmail);
                        setOtpSent(true);
                        setOtpMessage(res.message || `Verification code sent to ${cleanEmail}. Check your inbox!`);
                    } catch (otpErr) {
                        setError(otpErr.message || 'Failed to send OTP code to email.');
                    }
                    setFormLoading(false);
                    return;
                }

                // Step 2: Verify 6-digit OTP code if not already verified
                if (!otpVerified) {
                    if (!otpCode.trim() || otpCode.trim().length !== 6) {
                        setError('Please enter the 6-digit OTP code sent to your email.');
                        setFormLoading(false);
                        return;
                    }

                    try {
                        await verifyOTP(cleanEmail, otpCode.trim(), cleanPassword, displayName.trim());
                        setOtpVerified(true);
                    } catch (vErr) {
                        setError(vErr.message || 'Invalid or expired OTP code.');
                        setFormLoading(false);
                        return;
                    }
                }

                // Complete registration — user is registered & auto-logged in
                try {
                    await register(cleanEmail, cleanPassword, displayName.trim());
                } catch (regErr) {
                    setError(regErr.message || 'Registration failed. Please try again.');
                    setFormLoading(false);
                    return;
                }
                
                // If a referral code was provided, link it after registration
                if (referralCode.trim()) {
                    try {
                        const token = await getToken();
                        const apiUrl = getApiUrl();
                        await fetch(`${apiUrl}/api/referrals/register`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'Authorization': `Bearer ${token}`
                            },
                            body: JSON.stringify({ referral_code: referralCode.trim() })
                        });
                    } catch (_refErr) {
                        // Non-fatal — don't block registration success
                    }
                }
            }
        } catch (err) {
            // Handled in AuthContext error
        } finally {
            setFormLoading(false);
        }
    };

    const handleResendVerification = async () => {
        setResendStatus('Sending...');
        try {
            const sent = await resendVerificationEmail();
            if (sent) {
                setResendStatus('✓ Verification link sent to your inbox!');
            } else {
                setResendStatus('Unable to send. Please try logging in first.');
            }
        } catch (err) {
            setResendStatus('Failed to send verification email. Please try again later.');
        }
    };

    const handleResendOTP = async (e) => {
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        const cleanEmail = email.trim().toLowerCase();
        if (!cleanEmail) {
            setError('Please enter a valid email address.');
            return;
        }

        setError('');
        setResendOtpLoading(true);
        setOtpMessage('Sending new verification code...');

        try {
            const res = mode === 'forgot' ? await sendResetOTP(cleanEmail) : await sendOTP(cleanEmail);
            setOtpCode('');
            setOtpVerified(false);
            setOtpMessage(res.message || '✓ New verification code sent to your email!');
        } catch (err) {
            const msg = err.message || 'Failed to resend code.';
            if (msg.includes('rate') || msg.includes('minute') || msg.includes('429')) {
                setError('Please wait a moment before requesting another code.');
            } else {
                setError(msg);
            }
            setOtpMessage('Failed to resend. Please try again.');
        } finally {
            setResendOtpLoading(false);
        }
    };

    const handleGoogleSignIn = (e) => {
        // Prevent default and stop propagation to ensure popup is user-initiated
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        setError('');
        setFormLoading(true);

        // Call loginWithGoogle directly - must be synchronous from click handler
        loginWithGoogle()
            .then(() => {
                // AuthContext will handle redirect
            })
            .catch((err) => {
                // Handle popup-blocked specifically with better UX
                if (err.code === 'auth/popup-blocked') {
                    setError('Pop-up blocked! Please allow pop-ups for this site. Click the icon in your browser address bar to enable.');
                } else {
                    setError(err.message || 'Google sign-in failed. Please try again.');
                }
                setFormLoading(false);
            });
    };

    if (authLoading) {
        return (
            <div className="auth-page-cyan">
                <div className="auth-container-cyan" style={{ textAlign: 'center', padding: '4rem 3rem' }}>
                    <div className="loading-spinner-cyan" style={{ width: '40px', height: '40px', margin: '0 auto 1.5rem' }}></div>
                    <p style={{ color: 'var(--text-secondary)' }}>Decrypting credentials...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="term-wrapper" style={{ padding: '0', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div className="term-window" style={{ maxWidth: '960px' }}>
                {/* Titlebar */}
                <div className="term-titlebar">
                  <div className="term-tab" onClick={() => navigate('/')}>
                    <span className="term-tab-icon" style={{color: '#3b78ff'}}>&gt;_</span>
                    <span className="term-tab-title">Home</span>
                  </div>
                  <div className="term-tab" onClick={() => navigate('/features')}>
                    <span className="term-tab-icon" style={{color: '#f9f1a5'}}>#</span>
                    <span className="term-tab-title">Features</span>
                  </div>
                  <div className="term-tab" onClick={() => navigate('/about')}>
                    <span className="term-tab-icon" style={{color: '#B266FF'}}>@</span>
                    <span className="term-tab-title">About</span>
                  </div>
                  <div className="term-tab" onClick={() => navigate('/pricing')}>
                    <span className="term-tab-icon" style={{color: '#16c60c'}}>$</span>
                    <span className="term-tab-title">Pricing</span>
                  </div>
                  <div className="term-tab" onClick={() => navigate('/docs')}>
                    <span className="term-tab-icon" style={{color: '#5bc0de'}}>?</span>
                    <span className="term-tab-title">Docs</span>
                  </div>
                  <div className="term-tab" onClick={() => navigate('/changelog')}>
                    <span className="term-tab-icon" style={{color: '#E5FF00'}}>↻</span>
                    <span className="term-tab-title">Changelog</span>
                  </div>
                  <div className="term-tab" onClick={() => navigate('/contacts')}>
                    <span className="term-tab-icon" style={{color: '#FF8C00'}}>~</span>
                    <span className="term-tab-title">Contacts</span>
                  </div>
                  <div className="term-tab" onClick={() => navigate('/referral')}>
                    <span className="term-tab-icon" style={{color: '#00FF66'}}>%</span>
                    <span className="term-tab-title">Referrals</span>
                  </div>
                  <div className="term-tab active">
                    <span className="term-tab-icon" style={{color: '#e74856'}}>*</span>
                    <span className="term-tab-title">Sign In</span>
                  </div>
                  <div className="term-tab-add">+</div>
                  <div className="term-tab-chevron">v</div>
                  <div className="term-window-controls">
                    <div className="term-ctrl">_</div>
                    <div className="term-ctrl">□</div>
                    <div className="term-ctrl close" onClick={() => navigate('/')}>×</div>
                  </div>
                </div>

                <div className="term-content" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 'auto', padding: '32px' }}>
                    <div className="term-md-card" style={{ maxWidth: '440px', width: '100%', margin: '20px auto', padding: '28px', border: '1px solid rgba(255, 255, 255, 0.07)', borderRadius: '12px', background: '#0a0a0a' }}>
                        <div className="term-md-tag" style={{ color: '#e74856', textAlign: 'center', marginBottom: '14px', fontSize: '0.8rem', fontWeight: 'bold' }}>[AUTHENTICATION REQUIRED]</div>
                        <h2 className="term-md-title" style={{ textAlign: 'center', fontSize: '1.4rem', marginBottom: '8px', color: '#fff' }}># {mode === 'signin' ? 'System Access' : 'Initialize Node'}</h2>
                        <p style={{ color: '#555', textAlign: 'center', fontSize: '0.88rem', marginBottom: '24px' }}>
                          {mode === 'signin' ? 'Enter credentials to resume session' : 'Create a new developer identity'}
                        </p>

                        {isCliFlow && (
                            <div style={{ background: 'rgba(39, 201, 63, 0.1)', border: '1px solid rgba(39, 201, 63, 0.3)', color: '#27c93f', padding: '8px 12px', borderRadius: '6px', fontSize: '0.85rem', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span style={{ fontWeight: 'bold' }}>➔</span>{' '}
                              {redirectUrl
                                ? 'Sign in to authorize your UTIM CLI terminal'
                                : 'Secured handshake to CLI client detected'}
                            </div>
                        )}

                        {/* Tab Switcher */}
                        <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', background: 'rgba(255,255,255,0.02)', padding: '4px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.04)' }}>
                          <button 
                            type="button"
                            style={{ flex: 1, background: mode === 'signin' ? 'rgba(255,255,255,0.05)' : 'transparent', border: 'none', color: mode === 'signin' ? '#fff' : '#555', padding: '8px', borderRadius: '6px', cursor: 'pointer', fontFamily: 'inherit', fontSize: '0.85rem', fontWeight: 'bold' }}
                            onClick={() => { setMode('signin'); setError(''); setOtpSent(false); }}
                          >
                            Log In
                          </button>
                          <button 
                            type="button"
                            style={{ flex: 1, background: mode === 'signup' ? 'rgba(255,255,255,0.05)' : 'transparent', border: 'none', color: mode === 'signup' ? '#fff' : '#555', padding: '8px', borderRadius: '6px', cursor: 'pointer', fontFamily: 'inherit', fontSize: '0.85rem', fontWeight: 'bold' }}
                            onClick={() => { setMode('signup'); setError(''); setOtpSent(false); }}
                          >
                            Register
                          </button>
                          <button 
                            type="button"
                            style={{ flex: 1, background: mode === 'forgot' ? 'rgba(255,255,255,0.05)' : 'transparent', border: 'none', color: mode === 'forgot' ? '#fff' : '#555', padding: '8px', borderRadius: '6px', cursor: 'pointer', fontFamily: 'inherit', fontSize: '0.85rem', fontWeight: 'bold' }}
                            onClick={() => { setMode('forgot'); setError(''); setOtpSent(false); }}
                          >
                            Reset
                          </button>
                        </div>

                        {error && (
                            <div style={{ background: 'rgba(231, 72, 86, 0.1)', border: '1px solid rgba(231, 72, 86, 0.3)', color: '#e74856', padding: '10px 14px', borderRadius: '6px', fontSize: '0.85rem', marginBottom: '16px' }}>
                              <div>[!] ERROR: {error}</div>
                              {mode === 'signin' && (
                                  <div style={{ marginTop: '10px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                      <button
                                          type="button"
                                          onClick={() => { setMode('forgot'); setError(''); setOtpSent(false); setOtpCode(''); }}
                                          style={{ background: 'rgba(96, 165, 250, 0.15)', border: '1px solid rgba(96, 165, 250, 0.4)', color: '#93c5fd', padding: '4px 10px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.78rem', fontWeight: 'bold' }}
                                      >
                                          🔑 Reset Passphrase
                                      </button>
                                      <button
                                          type="button"
                                          onClick={() => { setMode('signup'); setError(''); setOtpSent(false); }}
                                          style={{ background: 'rgba(255, 255, 255, 0.08)', border: '1px solid rgba(255, 255, 255, 0.2)', color: '#fff', padding: '4px 10px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.78rem', fontWeight: 'bold' }}
                                      >
                                          📝 Register Account
                                      </button>
                                  </div>
                              )}
                            </div>
                        )}

                        {verificationSent && (
                            <div style={{ background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.3)', color: '#60a5fa', padding: '14px 16px', borderRadius: '8px', fontSize: '0.88rem', marginBottom: '20px', lineHeight: '1.5' }}>
                                <div style={{ fontWeight: 'bold', marginBottom: '4px', fontSize: '0.95rem', color: '#93c5fd' }}>
                                  ✉️ Verification Email Sent!
                                </div>
                                A verification link has been sent to your email inbox. Please click the link to verify your account before accessing UTIM.
                                <div style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                                  <button
                                    type="button"
                                    onClick={handleResendVerification}
                                    style={{ background: 'transparent', border: '1px solid rgba(147, 197, 253, 0.4)', color: '#93c5fd', padding: '4px 10px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 'bold' }}
                                  >
                                    Resend Verification Email
                                  </button>
                                  {resendStatus && <span style={{ fontSize: '0.8rem', color: '#a7f3d0' }}>{resendStatus}</span>}
                                </div>
                            </div>
                        )}

                        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                            {mode === 'signup' && (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                    <label style={{ fontSize: '0.75rem', color: '#666', fontWeight: 'bold', textTransform: 'uppercase' }}>Developer Name</label>
                                    <input
                                        type="text"
                                        style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.08)', padding: '10px 12px', borderRadius: '6px', color: '#fff', fontSize: '0.9rem', outline: 'none', fontFamily: 'inherit' }}
                                        placeholder="Jane Doe"
                                        value={displayName}
                                        onChange={(e) => setDisplayName(e.target.value)}
                                        disabled={formLoading}
                                    />
                                </div>
                            )}

                            {mode === 'signup' && (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                    <label style={{ fontSize: '0.75rem', color: '#444', fontWeight: 'bold', textTransform: 'uppercase' }}>Referral Code <span style={{ color: '#333', fontWeight: 'normal', textTransform: 'none' }}>(optional)</span></label>
                                    <input
                                        type="text"
                                        style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.05)', padding: '10px 12px', borderRadius: '6px', color: '#aaa', fontSize: '0.9rem', outline: 'none', fontFamily: 'monospace' }}
                                        placeholder="e.g. a1b2c3d4"
                                        value={referralCode}
                                        onChange={(e) => setReferralCode(e.target.value)}
                                        disabled={formLoading}
                                    />
                                </div>
                            )}

                            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                <label style={{ fontSize: '0.75rem', color: '#666', fontWeight: 'bold', textTransform: 'uppercase' }}>Email Address</label>
                                <input
                                    type="email"
                                    style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.08)', padding: '10px 12px', borderRadius: '6px', color: '#fff', fontSize: '0.9rem', outline: 'none', fontFamily: 'inherit' }}
                                    placeholder="jane@example.com"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    required
                                    disabled={formLoading}
                                />
                            </div>

                            {mode === 'signin' && (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                    <label style={{ fontSize: '0.75rem', color: '#666', fontWeight: 'bold', textTransform: 'uppercase' }}>Passphrase</label>
                                    <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                                        <input
                                            type={showPassword ? 'text' : 'password'}
                                            style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.08)', padding: '10px 40px 10px 12px', borderRadius: '6px', color: '#fff', fontSize: '0.9rem', outline: 'none', fontFamily: 'inherit', width: '100%' }}
                                            placeholder="••••••••"
                                            value={password}
                                            onChange={(e) => setPassword(e.target.value)}
                                            required
                                            minLength={6}
                                            disabled={formLoading}
                                        />
                                        <button
                                            type="button"
                                            onClick={() => setShowPassword(!showPassword)}
                                            style={{ position: 'absolute', right: '10px', background: 'none', border: 'none', color: '#888', cursor: 'pointer', fontSize: '0.9rem', padding: '4px' }}
                                            title={showPassword ? 'Hide Passphrase' : 'Show Passphrase'}
                                        >
                                            {showPassword ? '🙈' : '👁️'}
                                        </button>
                                    </div>
                                    <div style={{ textAlign: 'right', marginTop: '2px' }}>
                                        <button
                                            type="button"
                                            style={{ background: 'none', border: 'none', color: '#60a5fa', cursor: 'pointer', fontSize: '0.78rem', textDecoration: 'underline' }}
                                            onClick={() => { setMode('forgot'); setError(''); setOtpSent(false); setOtpCode(''); setLoginNeedsOtp(false); }}
                                        >
                                            Forgot Passphrase?
                                        </button>
                                    </div>
                                </div>
                            )}

                            {/* Login OTP recovery — shown when email is unverified */}
                            {mode === 'signin' && loginNeedsOtp && (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', background: 'rgba(59, 130, 246, 0.08)', border: '1px solid rgba(59, 130, 246, 0.3)', padding: '16px', borderRadius: '10px' }}>
                                    <div style={{ color: '#93c5fd', fontWeight: 'bold', fontSize: '0.85rem' }}>
                                        📬 Email Verification Required
                                    </div>
                                    <div style={{ color: '#6b9fd4', fontSize: '0.82rem', lineHeight: '1.5' }}>
                                        {otpMessage}
                                    </div>
                                    <label style={{ fontSize: '0.72rem', color: '#60a5fa', fontWeight: 'bold', textTransform: 'uppercase', marginTop: '4px' }}>
                                        Enter 6-Digit Code
                                    </label>
                                    <input
                                        type="text"
                                        style={{ background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(96, 165, 250, 0.5)', padding: '12px', borderRadius: '6px', color: '#60a5fa', fontSize: '1.4rem', fontWeight: 'bold', letterSpacing: '8px', textAlign: 'center', outline: 'none', fontFamily: 'monospace' }}
                                        placeholder="123456"
                                        maxLength={6}
                                        value={loginOtpCode}
                                        onChange={(e) => setLoginOtpCode(e.target.value.replace(/\D/g, ''))}
                                        disabled={formLoading || loginOtpVerifying}
                                        autoFocus
                                    />
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.78rem', color: '#6b7280' }}>
                                        <span>Didn't get the code?</span>
                                        <button
                                            type="button"
                                            onClick={async () => { try { await sendOTP(email.trim().toLowerCase()); } catch (_) {} }}
                                            style={{ background: 'none', border: 'none', color: '#60a5fa', cursor: 'pointer', fontSize: '0.78rem', textDecoration: 'underline' }}
                                        >
                                            Resend Code
                                        </button>
                                    </div>
                                </div>
                            )}


                            {mode === 'signup' && (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                    <label style={{ fontSize: '0.75rem', color: '#666', fontWeight: 'bold', textTransform: 'uppercase' }}>Passphrase</label>
                                    <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                                        <input
                                            type={showPassword ? 'text' : 'password'}
                                            style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.08)', padding: '10px 40px 10px 12px', borderRadius: '6px', color: '#fff', fontSize: '0.9rem', outline: 'none', fontFamily: 'inherit', width: '100%' }}
                                            placeholder="••••••••"
                                            value={password}
                                            onChange={(e) => setPassword(e.target.value)}
                                            required
                                            minLength={6}
                                            disabled={formLoading}
                                        />
                                        <button
                                            type="button"
                                            onClick={() => setShowPassword(!showPassword)}
                                            style={{ position: 'absolute', right: '10px', background: 'none', border: 'none', color: '#888', cursor: 'pointer', fontSize: '0.9rem', padding: '4px' }}
                                            title={showPassword ? 'Hide Passphrase' : 'Show Passphrase'}
                                        >
                                            {showPassword ? '🙈' : '👁️'}
                                        </button>
                                    </div>
                                </div>
                            )}

                            {mode === 'signup' && otpSent && (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', background: 'rgba(59, 130, 246, 0.08)', border: '1px solid rgba(59, 130, 246, 0.25)', padding: '14px', borderRadius: '8px' }}>
                                    <label style={{ fontSize: '0.75rem', color: '#60a5fa', fontWeight: 'bold', textTransform: 'uppercase' }}>
                                      🔐 6-Digit OTP Verification Code
                                    </label>
                                    <div style={{ fontSize: '0.8rem', color: '#93c5fd', marginBottom: '4px' }}>
                                      {otpMessage}
                                    </div>
                                    <input
                                        type="text"
                                        style={{ background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(96, 165, 250, 0.4)', padding: '10px 12px', borderRadius: '6px', color: '#60a5fa', fontSize: '1.2rem', fontWeight: 'bold', letterSpacing: '6px', textAlign: 'center', outline: 'none', fontFamily: 'monospace' }}
                                        placeholder="123456"
                                        maxLength={6}
                                        value={otpCode}
                                        onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                                        disabled={formLoading}
                                        required
                                    />
                                    <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '4px', display: 'flex', justifyContent: 'space-between' }}>
                                        <span>Didn't get code?</span>
                                        <button
                                          type="button"
                                          style={{ background: 'none', border: 'none', color: '#60a5fa', cursor: resendOtpLoading ? 'not-allowed' : 'pointer', fontSize: '0.75rem', textDecoration: 'underline' }}
                                          onClick={handleResendOTP}
                                          disabled={resendOtpLoading}
                                        >
                                          {resendOtpLoading ? 'Sending...' : 'Resend OTP Code'}
                                        </button>
                                    </div>
                                </div>
                            )}

                            {mode === 'forgot' && otpSent && (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', background: 'rgba(59, 130, 246, 0.08)', border: '1px solid rgba(59, 130, 246, 0.25)', padding: '14px', borderRadius: '8px' }}>
                                        <label style={{ fontSize: '0.75rem', color: '#60a5fa', fontWeight: 'bold', textTransform: 'uppercase' }}>
                                          🔐 6-Digit Reset Code
                                        </label>
                                        <div style={{ fontSize: '0.8rem', color: '#93c5fd', marginBottom: '4px' }}>
                                          {otpMessage}
                                        </div>
                                        <input
                                            type="text"
                                            style={{ background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(96, 165, 250, 0.4)', padding: '10px 12px', borderRadius: '6px', color: '#60a5fa', fontSize: '1.2rem', fontWeight: 'bold', letterSpacing: '6px', textAlign: 'center', outline: 'none', fontFamily: 'monospace' }}
                                            placeholder="123456"
                                            maxLength={6}
                                            value={otpCode}
                                            onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                                            disabled={formLoading}
                                            required
                                        />
                                        <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '4px', display: 'flex', justifyContent: 'space-between' }}>
                                            <span>Didn't get code?</span>
                                            <button
                                              type="button"
                                              style={{ background: 'none', border: 'none', color: '#60a5fa', cursor: resendOtpLoading ? 'not-allowed' : 'pointer', fontSize: '0.75rem', textDecoration: 'underline' }}
                                              onClick={handleResendOTP}
                                              disabled={resendOtpLoading}
                                            >
                                              {resendOtpLoading ? 'Sending...' : 'Resend Code'}
                                            </button>
                                        </div>
                                    </div>

                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                        <label style={{ fontSize: '0.75rem', color: '#666', fontWeight: 'bold', textTransform: 'uppercase' }}>New Passphrase</label>
                                        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                                            <input
                                                type={showPassword ? 'text' : 'password'}
                                                style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.08)', padding: '10px 40px 10px 12px', borderRadius: '6px', color: '#fff', fontSize: '0.9rem', outline: 'none', fontFamily: 'inherit', width: '100%' }}
                                                placeholder="••••••••"
                                                value={newPassword}
                                                onChange={(e) => setNewPassword(e.target.value)}
                                                required
                                                minLength={6}
                                                disabled={formLoading}
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowPassword(!showPassword)}
                                                style={{ position: 'absolute', right: '10px', background: 'none', border: 'none', color: '#888', cursor: 'pointer', fontSize: '0.9rem', padding: '4px' }}
                                                title={showPassword ? 'Hide Passphrase' : 'Show Passphrase'}
                                            >
                                                {showPassword ? '🙈' : '👁️'}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            )}

                            <button
                                type="submit"
                                style={{ background: loginNeedsOtp ? '#2563eb' : '#e74856', border: 'none', color: '#fff', padding: '12px', borderRadius: '6px', fontSize: '0.9rem', fontWeight: 'bold', cursor: 'pointer', outline: 'none', fontFamily: 'inherit', marginTop: '8px' }}
                                disabled={formLoading || loginOtpVerifying}
                            >
                                {formLoading || loginOtpVerifying
                                    ? 'Executing...'
                                    : loginNeedsOtp
                                        ? 'VERIFY & SIGN IN'
                                        : mode === 'signin'
                                            ? 'EXECUTE.LOGIN()'
                                            : mode === 'forgot'
                                                ? (!otpSent ? 'SEND RESET OTP' : 'RESET PASSPHRASE & LOGIN')
                                                : (!otpSent ? 'SEND OTP CODE' : 'VERIFY OTP & REGISTER')}
                            </button>
                        </form>

                        <div style={{ display: 'flex', alignItems: 'center', margin: '20px 0', color: '#333', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '1px' }}>
                            <div style={{ flexGrow: 1, height: '1px', background: 'rgba(255,255,255,0.04)' }}></div>
                            <span style={{ padding: '0 10px' }}>OR EXTERNALLY AUTHENTICATE</span>
                            <div style={{ flexGrow: 1, height: '1px', background: 'rgba(255,255,255,0.04)' }}></div>
                        </div>

                        <button
                            type="button"
                            style={{ width: '100%', padding: '10px', background: 'transparent', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '6px', color: '#fff', fontWeight: '600', fontSize: '0.9rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', cursor: 'pointer', fontFamily: 'inherit' }}
                            onClick={handleGoogleSignIn}
                            disabled={formLoading}
                        >
                            <svg style={{ width: '18px', height: '18px' }} viewBox="0 0 24 24">
                                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                            </svg>
                            Google OAuth
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default AuthPage;
