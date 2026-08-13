import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { getApiUrl } from '../../lib/api';
import ScrollytellingHeaderNav from '../../components/ScrollytellingHeaderNav';
import ScrollytellingFooter from '../../components/ScrollytellingFooter';
import SEOHead from '../../components/SEOHead';
import { Sparkles, Mail, MailOpen, Lock, User, Key, Check, AlertCircle, ArrowRight, ShieldCheck, Eye, EyeOff, ChevronLeft } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import '../../components/ScrollytellingMain.css';

export default function AuthPage() {
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
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [resetEmailSent, setResetEmailSent] = useState(false);
  
  // Login-page OTP recovery
  const [loginNeedsOtp, setLoginNeedsOtp] = useState(false);
  const [loginOtpCode, setLoginOtpCode] = useState('');
  const [loginOtpVerifying, setLoginOtpVerifying] = useState(false);

  const [oobCode, setOobCode] = useState(null);

  const { 
    login, register, sendOTP, verifyOTP, 
    sendResetOTP, resetPasswordWithOTP, 
    verifyResetCode, confirmResetPassword,
    resendVerificationEmail, loginWithGoogle, 
    isAuthenticated, user, loading: authLoading, 
    error: authError, getToken 
  } = useAuth();
  
  const navigate = useNavigate();

  const callbackUrl = searchParams.get('callback');
  const redirectUrl = searchParams.get('redirect');
  const isCliFlow = !!callbackUrl || !!redirectUrl;

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

  useEffect(() => {
    if (authError) {
      setError(authError);
    }
  }, [authError]);

  useEffect(() => {
    const modeParam = searchParams.get('mode');
    const oobCodeParam = searchParams.get('oobCode');
    if (modeParam === 'resetPassword' && oobCodeParam) {
      setOobCode(oobCodeParam);
      setMode('resetPassword');
      setFormLoading(true);
      verifyResetCode(oobCodeParam)
        .then((associatedEmail) => {
          setEmail(associatedEmail);
          setFormLoading(false);
        })
        .catch((err) => {
          setError(err.message || 'Your password reset link is invalid or has expired.');
          setFormLoading(false);
        });
    }
  }, [searchParams]);

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

    try {
      if (mode === 'signin') {
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
        } catch (loginErr) {
          const msg = loginErr.message || '';
          if (msg.toLowerCase().includes('not verified') || msg.toLowerCase().includes('forbidden') || msg.toLowerCase().includes('403')) {
            try { await sendOTP(cleanEmail); } catch (_) {}
            setLoginNeedsOtp(true);
            setLoginOtpCode('');
            setError('');
            setOtpMessage(`A 6-digit verification code has been sent to ${cleanEmail}. Enter it below to complete sign-in.`);
          } else if (msg.includes('Incorrect') || msg.includes('Invalid') || msg.includes('wrong-password') || msg.includes('user-not-found') || msg.includes('credential')) {
            setError('Incorrect email or password. Please double-check your credentials.');
          } else {
            setError(msg || 'Sign in failed. Please check your credentials.');
          }
        }
      } else if (mode === 'resetPassword') {
        if (!cleanNewPassword || cleanNewPassword.length < 6) {
          setError('New password must be at least 6 characters long.');
          setFormLoading(false);
          return;
        }

        if (cleanNewPassword !== confirmPassword.trim()) {
          setError('New passwords do not match. Please verify both fields.');
          setFormLoading(false);
          return;
        }

        try {
          await confirmResetPassword(oobCode, cleanNewPassword);
          setError('');
          setOtpMessage('Your password has been reset successfully! Signing you in...');
          await login(cleanEmail, cleanNewPassword);
        } catch (resetErr) {
          setError(resetErr.message || 'Failed to update password. The link may be expired.');
        }
        setFormLoading(false);
        return;
      } else if (mode === 'forgot') {
        try {
          const res = await sendResetOTP(cleanEmail);
          setResetEmailSent(true);
          setOtpMessage(res.message || `Password reset instructions have been dispatched to ${cleanEmail}. Check your inbox!`);
        } catch (otpErr) {
          setError(otpErr.message || 'Failed to send password reset link.');
        }
        setFormLoading(false);
        return;
      } else {
        // Sign Up Mode
        if (!displayName.trim()) {
          setError('Please enter your developer name.');
          setFormLoading(false);
          return;
        }

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

        try {
          await register(cleanEmail, cleanPassword, displayName.trim());
        } catch (regErr) {
          setError(regErr.message || 'Registration failed. Please try again.');
          setFormLoading(false);
          return;
        }
        
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
          } catch (_) {}
        }
      }
    } catch (err) {
      // Handled in context
    } finally {
      setFormLoading(false);
    }
  };

  const handleResendOTP = async (e) => {
    if (e) e.preventDefault();
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
      setError(err.message || 'Failed to resend code.');
    } finally {
      setResendOtpLoading(false);
    }
  };

  const handleGoogleSignIn = (e) => {
    if (e) e.preventDefault();
    setError('');
    setFormLoading(true);

    loginWithGoogle()
      .then(() => {})
      .catch((err) => {
        if (err.code === 'auth/popup-blocked') {
          setError('Pop-up blocked! Please allow pop-ups for this site to sign in with Google.');
        } else {
          setError(err.message || 'Google sign-in failed. Please try again.');
        }
        setFormLoading(false);
      });
  };  return (
    <div className="st-page-root" style={{ position: 'relative', overflow: 'hidden' }}>
      <SEOHead
        title="Sign In / Register — UTIM AI"
        description="Sign in or create your UTIM developer account to access autonomous terminal agents, manage quotas, and pair devices."
        canonical="https://utim.dev/auth"
      />
      
      <ScrollytellingHeaderNav />

      {/* Classy background glowing spots */}
      <div style={{ position: 'absolute', top: '12%', left: '8%', width: 340, height: 340, borderRadius: '50%', background: 'radial-gradient(circle, rgba(66,133,244,0.1) 0%, rgba(66,133,244,0) 70%)', filter: 'blur(60px)', zIndex: 0, pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', bottom: '15%', right: '8%', width: 380, height: 380, borderRadius: '50%', background: 'radial-gradient(circle, rgba(0,180,216,0.08) 0%, rgba(0,180,216,0) 70%)', filter: 'blur(70px)', zIndex: 0, pointerEvents: 'none' }} />

      <div style={{ padding: '60px 24px 100px 24px', display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 'calc(100vh - 180px)', zIndex: 1, position: 'relative' }}>
        <motion.div 
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          style={{ 
            background: 'rgba(255, 255, 255, 0.85)', 
            backdropFilter: 'blur(20px) saturate(190%)',
            border: '1px solid rgba(226, 232, 240, 0.8)', 
            borderRadius: 24, 
            boxShadow: '0 25px 50px -12px rgba(0,0,0,0.04), inset 0 1px 0 rgba(255,255,255,0.7)',
            maxWidth: 460, 
            width: '100%', 
            padding: '48px 40px' 
          }}
        >
          {resetEmailSent ? (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: 20 }}
            >
              <div style={{
                width: 60,
                height: 60,
                borderRadius: '50%',
                background: 'rgba(52,211,153,0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#059669',
                marginBottom: 4
              }}>
                <MailOpen size={30} />
              </div>
              <h2 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)', margin: 0, letterSpacing: '-0.01em' }}>
                Check Your Inbox
              </h2>
              <p style={{ fontSize: '0.92rem', color: 'var(--text-body)', lineHeight: 1.6, margin: 0 }}>
                {otpMessage || 'Password reset link sent! Check your inbox to complete the update.'}
              </p>
              
              <button
                type="button"
                onClick={() => {
                  setMode('signin');
                  setResetEmailSent(false);
                  setOtpSent(false);
                  setOtpMessage('');
                  setOtpCode('');
                  setNewPassword('');
                  setConfirmPassword('');
                  setError('');
                }}
                className="st-nav-primary-btn"
                style={{ width: '100%', padding: '12px', marginTop: 12, fontSize: 14.5, fontWeight: 700, borderRadius: 8, border: 'none', background: 'var(--text-primary)', color: '#FFFFFF', cursor: 'pointer' }}
              >
                Back to Sign In
              </button>
            </motion.div>
          ) : (
            <>
              {/* Back Navigation for Forgot Password */}
          {mode === 'forgot' && (
            <button
              type="button"
              onClick={() => { setMode('signin'); setError(''); setOtpSent(false); }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                background: 'none',
                border: 'none',
                color: 'var(--text-muted)',
                fontSize: 13,
                fontWeight: 700,
                cursor: 'pointer',
                marginBottom: 16,
                padding: '4px 0',
                transition: 'color 0.2s ease',
                outline: 'none'
              }}
              onMouseEnter={(e) => e.currentTarget.style.color = 'var(--text-primary)'}
              onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-muted)'}
            >
              <ChevronLeft size={16} /> Back to Sign In
            </button>
          )}

          {/* Badge & Title */}
          <div style={{ textAlign: 'center', marginBottom: 28 }}>
            <div className="st-hero-badge" style={{ display: 'inline-flex', marginBottom: 12 }}>
              <ShieldCheck size={14} /> DEVELOPER AUTHENTICATION
            </div>
            <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em', marginBottom: 6 }}>
              {mode === 'signin' ? 'Welcome Back' : mode === 'signup' ? 'Create Account' : mode === 'resetPassword' ? 'Update Password' : 'Reset Password'}
            </h1>
            <p style={{ fontSize: '0.92rem', color: 'var(--text-muted)' }}>
              {mode === 'signin' ? 'Enter credentials to manage your nodes and devices' : mode === 'signup' ? 'Get started with 1,000 free monthly credits' : mode === 'resetPassword' ? 'Enter and confirm your new developer password below' : 'Receive a 6-digit recovery code via email'}
            </p>
          </div>

          {/* CLI Handshake Notification */}
          {isCliFlow && (
            <div style={{ background: 'var(--bg-cream-alt)', border: '1px solid var(--border-cream)', padding: '12px 14px', borderRadius: 8, fontSize: 13, color: 'var(--text-primary)', marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Sparkles size={16} />
              <span>Sign in to authorize your local UTIM terminal session.</span>
            </div>
          )}

          {/* Tab Switcher (Only visible for Sign In / Register modes) */}
          {mode !== 'forgot' && mode !== 'resetPassword' && (
            <div style={{ display: 'flex', gap: 4, background: 'var(--bg-cream-alt)', padding: 4, borderRadius: 12, border: '1px solid var(--border-cream)', marginBottom: 24, position: 'relative' }}>
              <button
                type="button"
                onClick={() => { setMode('signin'); setError(''); setOtpSent(false); }}
                style={{
                  flex: 1,
                  padding: '10px 12px',
                  border: 'none',
                  borderRadius: 8,
                  fontSize: 13.5,
                  fontWeight: 700,
                  cursor: 'pointer',
                  background: 'transparent',
                  color: mode === 'signin' ? 'var(--text-primary)' : 'var(--text-muted)',
                  position: 'relative',
                  zIndex: 1,
                  transition: 'color 0.2s ease',
                  outline: 'none'
                }}
              >
                {mode === 'signin' && (
                  <motion.div
                    layoutId="active-auth-tab"
                    style={{
                      position: 'absolute',
                      inset: 0,
                      background: '#FFFFFF',
                      borderRadius: 8,
                      boxShadow: 'var(--shadow-sm)',
                      zIndex: -1
                    }}
                    transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                  />
                )}
                Sign In
              </button>
              <button
                type="button"
                onClick={() => { setMode('signup'); setError(''); setOtpSent(false); }}
                style={{
                  flex: 1,
                  padding: '10px 12px',
                  border: 'none',
                  borderRadius: 8,
                  fontSize: 13.5,
                  fontWeight: 700,
                  cursor: 'pointer',
                  background: 'transparent',
                  color: mode === 'signup' ? 'var(--text-primary)' : 'var(--text-muted)',
                  position: 'relative',
                  zIndex: 1,
                  transition: 'color 0.2s ease',
                  outline: 'none'
                }}
              >
                {mode === 'signup' && (
                  <motion.div
                    layoutId="active-auth-tab"
                    style={{
                      position: 'absolute',
                      inset: 0,
                      background: '#FFFFFF',
                      borderRadius: 8,
                      boxShadow: 'var(--shadow-sm)',
                      zIndex: -1
                    }}
                    transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                  />
                )}
                Register
              </button>
            </div>
          )}

          {/* Error Banner */}
          <AnimatePresence>
            {error && (
              <motion.div 
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: '#DC2626', padding: '10px 14px', borderRadius: 8, fontSize: 13, marginBottom: 18, display: 'flex', alignItems: 'center', gap: 8 }}
              >
                <AlertCircle size={16} style={{ flexShrink: 0 }} />
                <span>{error}</span>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Form */}
          <form onSubmit={handleSubmit}>
            <AnimatePresence mode="wait">
              <motion.div
                key={mode + (otpSent ? '-otp' : '')}
                initial={{ opacity: 0, x: 12 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -12 }}
                transition={{ duration: 0.22, ease: 'easeInOut' }}
                style={{ display: 'flex', flexDirection: 'column', gap: 16 }}
              >
                {mode === 'signup' && (
                  <div>
                    <label style={{ display: 'block', fontSize: 12.5, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      Developer Name
                    </label>
                    <div style={{ position: 'relative' }}>
                      <User size={16} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                      <input
                        type="text"
                        placeholder="Alex Mercer"
                        value={displayName}
                        onChange={(e) => setDisplayName(e.target.value)}
                        required
                        disabled={formLoading}
                        style={{ width: '100%', padding: '10px 12px 10px 36px', borderRadius: 8, border: '1px solid var(--border-cream)', background: 'var(--bg-cream-alt)', color: 'var(--text-primary)', fontSize: 14, outline: 'none', transition: 'border-color 0.2s ease, box-shadow 0.2s ease' }}
                        onFocus={(e) => { e.target.style.borderColor = 'var(--text-muted)'; e.target.style.boxShadow = '0 0 0 2px var(--border-cream)'; }}
                        onBlur={(e) => { e.target.style.borderColor = 'var(--border-cream)'; e.target.style.boxShadow = 'none'; }}
                      />
                    </div>
                  </div>
                )}

                {/* Email Field (Show for all modes, except forgot password after OTP is sent) */}
                {!(mode === 'forgot' && otpSent) && (
                  <div>
                    <label style={{ display: 'block', fontSize: 12.5, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      Email Address
                    </label>
                    <div style={{ position: 'relative' }}>
                      <Mail size={16} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                      <input
                        type="email"
                        placeholder="name@domain.com"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                        disabled={formLoading || mode === 'resetPassword'}
                        style={{ width: '100%', padding: '10px 12px 10px 36px', borderRadius: 8, border: '1px solid var(--border-cream)', background: 'var(--bg-cream-alt)', color: 'var(--text-primary)', fontSize: 14, outline: 'none', transition: 'border-color 0.2s ease, box-shadow 0.2s ease' }}
                        onFocus={(e) => { e.target.style.borderColor = 'var(--text-muted)'; e.target.style.boxShadow = '0 0 0 2px var(--border-cream)'; }}
                        onBlur={(e) => { e.target.style.borderColor = 'var(--border-cream)'; e.target.style.boxShadow = 'none'; }}
                      />
                    </div>
                  </div>
                )}

                {mode === 'signin' && (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                      <label style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                        Password
                      </label>
                      <button
                        type="button"
                        onClick={() => { setMode('forgot'); setError(''); setOtpSent(false); }}
                        style={{ background: 'none', border: 'none', color: 'var(--text-body)', fontSize: 12.5, fontWeight: 600, cursor: 'pointer', textDecoration: 'underline', outline: 'none' }}
                      >
                        Forgot Password?
                      </button>
                    </div>
                    <div style={{ position: 'relative' }}>
                      <Lock size={16} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                      <input
                        type={showPassword ? 'text' : 'password'}
                        placeholder="••••••••"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                        minLength={6}
                        disabled={formLoading}
                        style={{ width: '100%', padding: '10px 40px 10px 36px', borderRadius: 8, border: '1px solid var(--border-cream)', background: 'var(--bg-cream-alt)', color: 'var(--text-primary)', fontSize: 14, outline: 'none', transition: 'border-color 0.2s ease, box-shadow 0.2s ease' }}
                        onFocus={(e) => { e.target.style.borderColor = 'var(--text-muted)'; e.target.style.boxShadow = '0 0 0 2px var(--border-cream)'; }}
                        onBlur={(e) => { e.target.style.borderColor = 'var(--border-cream)'; e.target.style.boxShadow = 'none'; }}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', color: 'var(--text-muted)', outline: 'none' }}
                      >
                        {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>
                )}

                {mode === 'signup' && (
                  <div>
                    <label style={{ display: 'block', fontSize: 12.5, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      Create Password
                    </label>
                    <div style={{ position: 'relative' }}>
                      <Lock size={16} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                      <input
                        type={showPassword ? 'text' : 'password'}
                        placeholder="••••••••"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                        minLength={6}
                        disabled={formLoading}
                        style={{ width: '100%', padding: '10px 40px 10px 36px', borderRadius: 8, border: '1px solid var(--border-cream)', background: 'var(--bg-cream-alt)', color: 'var(--text-primary)', fontSize: 14, outline: 'none', transition: 'border-color 0.2s ease, box-shadow 0.2s ease' }}
                        onFocus={(e) => { e.target.style.borderColor = 'var(--text-muted)'; e.target.style.boxShadow = '0 0 0 2px var(--border-cream)'; }}
                        onBlur={(e) => { e.target.style.borderColor = 'var(--border-cream)'; e.target.style.boxShadow = 'none'; }}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', color: 'var(--text-muted)', outline: 'none' }}
                      >
                        {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>
                )}

                {mode === 'resetPassword' && (
                  <>
                    <div>
                      <label style={{ display: 'block', fontSize: 12.5, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                        New Password
                      </label>
                      <div style={{ position: 'relative' }}>
                        <Lock size={16} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                        <input
                          type={showNewPassword ? 'text' : 'password'}
                          placeholder="••••••••"
                          value={newPassword}
                          onChange={(e) => setNewPassword(e.target.value)}
                          required
                          minLength={6}
                          disabled={formLoading}
                          style={{ width: '100%', padding: '10px 40px 10px 36px', borderRadius: 8, border: '1px solid var(--border-cream)', background: 'var(--bg-cream-alt)', color: 'var(--text-primary)', fontSize: 14, outline: 'none', transition: 'border-color 0.2s ease, box-shadow 0.2s ease' }}
                          onFocus={(e) => { e.target.style.borderColor = 'var(--text-muted)'; e.target.style.boxShadow = '0 0 0 2px var(--border-cream)'; }}
                          onBlur={(e) => { e.target.style.borderColor = 'var(--border-cream)'; e.target.style.boxShadow = 'none'; }}
                        />
                        <button
                          type="button"
                          onClick={() => setShowNewPassword(!showNewPassword)}
                          style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', color: 'var(--text-muted)', outline: 'none' }}
                        >
                          {showNewPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                      </div>
                    </div>

                    <div>
                      <label style={{ display: 'block', fontSize: 12.5, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                        Confirm New Password
                      </label>
                      <div style={{ position: 'relative' }}>
                        <Lock size={16} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                        <input
                          type={showNewPassword ? 'text' : 'password'}
                          placeholder="••••••••"
                          value={confirmPassword}
                          onChange={(e) => setConfirmPassword(e.target.value)}
                          required
                          minLength={6}
                          disabled={formLoading}
                          style={{ width: '100%', padding: '10px 40px 10px 36px', borderRadius: 8, border: '1px solid var(--border-cream)', background: 'var(--bg-cream-alt)', color: 'var(--text-primary)', fontSize: 14, outline: 'none', transition: 'border-color 0.2s ease, box-shadow 0.2s ease' }}
                          onFocus={(e) => { e.target.style.borderColor = 'var(--text-muted)'; e.target.style.boxShadow = '0 0 0 2px var(--border-cream)'; }}
                          onBlur={(e) => { e.target.style.borderColor = 'var(--border-cream)'; e.target.style.boxShadow = 'none'; }}
                        />
                        <button
                          type="button"
                          onClick={() => setShowNewPassword(!showNewPassword)}
                          style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', color: 'var(--text-muted)', outline: 'none' }}
                        >
                          {showNewPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                      </div>
                    </div>
                  </>
                )}

                {/* Signup OTP Box */}
                {mode === 'signup' && otpSent && (
                  <div style={{ background: 'var(--bg-cream-alt)', border: '1px solid var(--border-cream)', padding: 16, borderRadius: 8 }}>
                    <label style={{ display: 'block', fontSize: 12.5, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>
                      Enter 6-Digit Email Code
                    </label>
                    <input
                      type="text"
                      placeholder="123456"
                      maxLength={6}
                      value={otpCode}
                      onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                      style={{ width: '100%', padding: '10px', textAlign: 'center', fontSize: 20, letterSpacing: 8, fontWeight: 800, borderRadius: 8, border: '1px solid var(--border-cream)', background: '#FFFFFF', color: 'var(--text-primary)', outline: 'none' }}
                    />
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8, fontSize: 12 }}>
                      <span style={{ color: 'var(--text-muted)' }}>Didn't receive code?</span>
                      <button
                        type="button"
                        onClick={handleResendOTP}
                        disabled={resendOtpLoading}
                        style={{ background: 'none', border: 'none', color: 'var(--text-primary)', fontWeight: 700, cursor: 'pointer', textDecoration: 'underline', outline: 'none' }}
                      >
                        {resendOtpLoading ? 'Sending...' : 'Resend Code'}
                      </button>
                    </div>
                  </div>
                )}



                {/* Login OTP Recovery */}
                {mode === 'signin' && loginNeedsOtp && (
                  <div style={{ background: 'var(--bg-cream-alt)', border: '1px solid var(--border-cream)', padding: 16, borderRadius: 8, marginTop: 4 }}>
                    <label style={{ display: 'block', fontSize: 12.5, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>
                      Enter 6-Digit Verification Code
                    </label>
                    <input
                      type="text"
                      placeholder="123456"
                      maxLength={6}
                      value={loginOtpCode}
                      onChange={(e) => setLoginOtpCode(e.target.value.replace(/\D/g, ''))}
                      style={{ width: '100%', padding: '10px', textAlign: 'center', fontSize: 20, letterSpacing: 8, fontWeight: 800, borderRadius: 8, border: '1px solid var(--border-cream)', background: '#FFFFFF', color: 'var(--text-primary)', outline: 'none' }}
                    />
                    {otpMessage && <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8, lineHeight: 1.5 }}>{otpMessage}</div>}
                  </div>
                )}

                {/* Status Message (If set and no error) */}
                {otpMessage && !error && !loginNeedsOtp && (
                  <div style={{ background: 'rgba(52,211,153,0.1)', border: '1px solid rgba(52,211,153,0.25)', color: '#059669', padding: '10px 14px', borderRadius: 8, fontSize: 13, lineHeight: 1.5 }}>
                    {otpMessage}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={formLoading || loginOtpVerifying}
                  className="st-nav-primary-btn"
                  style={{ width: '100%', padding: '12px', marginTop: 12, fontSize: 14.5, fontWeight: 700 }}
                >
                  {formLoading || loginOtpVerifying
                    ? 'Processing...'
                    : loginNeedsOtp
                      ? 'Verify & Sign In'
                      : mode === 'signin'
                        ? 'Sign In to Account'
                        : mode === 'forgot'
                          ? 'Send Reset Link'
                          : mode === 'resetPassword'
                            ? 'Update Password & Sign In'
                            : (!otpSent ? 'Send Verification Code' : 'Verify & Complete Registration')}
                </button>
              </motion.div>
            </AnimatePresence>
          </form>

          {/* Divider */}
          <div style={{ display: 'flex', alignItems: 'center', margin: '24px 0', gap: 12 }}>
            <div style={{ flex: 1, height: 1, background: 'var(--border-cream)' }}></div>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>OR</span>
            <div style={{ flex: 1, height: 1, background: 'var(--border-cream)' }}></div>
          </div>

          {/* Google Sign In Button */}
          <button
            type="button"
            onClick={handleGoogleSignIn}
            disabled={formLoading}
            style={{
              width: '100%',
              padding: '11px',
              borderRadius: 8,
              border: '1px solid var(--border-cream)',
              background: '#FFFFFF',
              color: 'var(--text-primary)',
              fontSize: 14,
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 10,
              boxShadow: 'var(--shadow-sm)'
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
            </svg>
            <span>Continue with Google</span>
          </button>
            </>
          )}
        </motion.div>
      </div>

      <ScrollytellingFooter />
    </div>
  );
}
