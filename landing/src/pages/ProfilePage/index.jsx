import React, { useEffect, useState, useRef } from 'react';
import { getApiUrl } from '../../lib/api';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { updateUserProfile } from '../../lib/firebase';
import CreditTopup from '../../components/CreditTopup';
import '../../components/PowershellUI/PowershellUI.css';
import './ProfilePage.css';

const PLAN_DISPLAY_MAP = {
    free: "Free",
    hobby: "Hobbyist Node",
    pro: "Starter Node",
    max: "Professional Core",
    ultimate: "MAX Node"
};

const ProfilePage = () => {
    const { user, userProfile, loading, logout, isAuthenticated } = useAuth();
    const navigate = useNavigate();
    const [uploading, setUploading] = useState(false);
    const [profilePic, setProfilePic] = useState(null);
    const [realPlan, setRealPlan] = useState(userProfile?.plan || 'free');
    const [usageData, setUsageData] = useState(null);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [emailInput, setEmailInput] = useState('');
    const [passwordInput, setPasswordInput] = useState('');
    const [deleting, setDeleting] = useState(false);
    const [reauthenticated, setReauthenticated] = useState(false);
    const [modalError, setModalError] = useState('');
    const fileInputRef = useRef(null);

    // Redirect if not authenticated
    useEffect(() => {
        if (!loading && !isAuthenticated) {
            navigate('/auth');
        }
    }, [loading, isAuthenticated, navigate]);

    // Fetch accurate plan & usage stats from backend
    useEffect(() => {
        const fetchUserData = async () => {
            if (user) {
                try {
                    const token = await user.getIdToken();
                    const apiUrl = getApiUrl();
                    
                    // Fetch Plan
                    const planRes = await fetch(`${apiUrl}/api/user-plan`, {
                        headers: { 'Authorization': `Bearer ${token}` }
                    });
                    if (planRes.ok) {
                        const data = await planRes.json();
                        if (data.plan) {
                            setRealPlan(data.plan);
                        }
                    }

                    // Fetch Usage (/api/usage)
                    const usageRes = await fetch(`${apiUrl}/api/usage`, {
                        headers: { 'Authorization': `Bearer ${token}` }
                    });
                    if (usageRes.ok) {
                        const usageJson = await usageRes.json();
                        setUsageData(usageJson);
                    }
                } catch (err) {
                    console.error('Failed to fetch user data/usage', err);
                }
            }
        };
        fetchUserData();
    }, [user]);

    // Set initial profile pic from user data
    useEffect(() => {
        if (user?.photoURL) {
            setProfilePic(user.photoURL);
        } else if (userProfile?.photoURL) {
            setProfilePic(userProfile.photoURL);
        }
    }, [user, userProfile]);

    const handleLogout = async () => {
        await logout();
        navigate('/');
    };

    const isGoogle = user?.providerData?.some(p => p.providerId === 'google.com');
    const isPassword = user?.providerData?.some(p => p.providerId === 'password');

    const handleDeleteAccount = () => {
        setIsModalOpen(true);
        setEmailInput('');
        setPasswordInput('');
        setReauthenticated(false);
        setModalError('');
    };

    const handleProfilePicClick = () => {
        fileInputRef.current?.click();
    };

    const handleFileChange = async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;

        if (!file.type.startsWith('image/')) {
            alert('Please select an image file');
            return;
        }

        if (file.size > 2 * 1024 * 1024) {
            alert('Image must be less than 2MB');
            return;
        }

        setUploading(true);

        try {
            const reader = new FileReader();
            reader.onload = async (event) => {
                const base64 = event.target?.result;
                const img = new Image();
                img.onload = async () => {
                    const canvas = document.createElement('canvas');
                    const maxSize = 200;
                    let width = img.width;
                    let height = img.height;

                    if (width > height) {
                        if (width > maxSize) {
                            height *= maxSize / width;
                            width = maxSize;
                        }
                    } else {
                        if (height > maxSize) {
                            width *= maxSize / height;
                            height = maxSize;
                        }
                    }

                    canvas.width = width;
                    canvas.height = height;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, width, height);

                    const compressedBase64 = canvas.toDataURL('image/jpeg', 0.8);
                    await updateUserProfile(user.uid, { photoURL: compressedBase64 });
                    setProfilePic(compressedBase64);
                    setUploading(false);
                };
                img.src = base64;
            };
            reader.readAsDataURL(file);
        } catch (error) {
            console.error('Error uploading profile picture:', error);
            alert('Failed to upload image. Please try again.');
            setUploading(false);
        }
    };

    if (loading) {
        return (
            <div className="term-wrapper" style={{ padding: '0', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <div className="term-window" style={{ maxWidth: '1000px', height: 'auto', minHeight: '400px' }}>
                    <div className="term-titlebar">
                        <div className="term-tab active">
                            <span className="term-tab-icon" style={{color: '#16c60c'}}>$</span>
                            <span className="term-tab-title">Loading...</span>
                        </div>
                    </div>
                    <div className="term-content" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '300px' }}>
                        <div className="term-line term-loading">
                            <span className="term-dot">.</span>
                            <span className="term-dot">.</span>
                            <span className="term-dot">.</span>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    if (!user) return null;

    const resolveDate = (value) => {
        if (!value) return null;
        if (value instanceof Date) return value;
        if (typeof value.toDate === 'function') return value.toDate();
        if (typeof value.toMillis === 'function') return new Date(value.toMillis());
        if (typeof value === 'object' && typeof value.seconds === 'number') {
            return new Date(value.seconds * 1000);
        }
        if (typeof value === 'string' || typeof value === 'number') {
            const parsed = new Date(value);
            return Number.isNaN(parsed.getTime()) ? null : parsed;
        }
        return null;
    };

    const formatDate = (value) => {
        const date = resolveDate(value);
        if (!date) return 'N/A';
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    };

    const formatRefillTime = (seconds) => {
        if (!seconds || seconds <= 0) return 'Now';
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${minutes}m`;
    };

    const memberSinceDate = userProfile?.createdAt || user?.metadata?.creationTime;
    const lastLoginDate = userProfile?.lastLoginAt || user?.metadata?.lastSignInTime;

    return (
        <div className="term-wrapper">
            <div className="term-window">
                {/* Modern Terminal Window Titlebar */}
                {/* Full nav bar — matches PowershellUI */}
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
                        <span className="term-tab-icon" style={{color: '#16c60c'}}>$</span>
                        <span className="term-tab-title">Profile</span>
                    </div>
                    <div className="term-tab-add">+</div>
                    <div className="term-tab-chevron">v</div>
                    <div className="term-window-controls">
                        <div className="term-ctrl">_</div>
                        <div className="term-ctrl">□</div>
                        <div className="term-ctrl close" onClick={() => navigate('/')}>×</div>
                    </div>
                </div>

                <div className="term-content term-markdown-view" style={{ padding: '32px' }}>
                    
                    {/* Markdown Header */}
                    <div className="term-md-header" style={{ marginBottom: '24px' }}>
                        <div className="term-md-tag">[DEVELOPER NODE IDENTIFIER]</div>
                        <h1 className="term-md-title" style={{ fontSize: '1.6rem', margin: '8px 0' }}>
                            # User Profile: {userProfile?.displayName || user.displayName || 'UTIM User'}
                        </h1>
                        <div className="term-md-subtitle" style={{ color: '#666', fontSize: '0.9rem' }}>
                            Authenticated Developer Identity • Connected to UTIM Cloud Server
                        </div>
                    </div>

                    <div className="term-md-divider">================================================================================</div>

                    {/* User Summary Card */}
                    <div className="term-md-card" style={{ marginBottom: '28px' }}>
                        <div className="term-md-card-border-top">┌── NODE IDENTITY ─────────────────────────────────────────────────────────────</div>
                        <div className="term-md-card-content" style={{ display: 'flex', alignItems: 'center', gap: '24px', padding: '16px 20px' }}>
                            <div
                                className="profile-avatar-term"
                                onClick={handleProfilePicClick}
                                title="Click to change profile picture"
                            >
                                {uploading ? (
                                    <div className="avatar-uploading-term">...</div>
                                ) : profilePic ? (
                                    <img src={profilePic} alt="Profile" />
                                ) : (
                                    <div className="default-avatar-term">
                                        {(user.displayName || user.email || 'U')[0].toUpperCase()}
                                    </div>
                                )}
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    onChange={handleFileChange}
                                    accept="image/*"
                                    style={{ display: 'none' }}
                                />
                            </div>
                            <div style={{ flex: 1 }}>
                                <div style={{ color: '#fff', fontSize: '1.1rem', fontWeight: 'bold' }}>
                                    {userProfile?.displayName || user.displayName || 'UTIM Developer'}
                                </div>
                                <div style={{ color: '#00F0FF', fontSize: '0.9rem', fontFamily: 'monospace', marginTop: '4px' }}>
                                    {user.email}
                                </div>
                            </div>
                            <div>
                                <span className={`term-plan-badge ${realPlan.toLowerCase()}`}>
                                    [{(PLAN_DISPLAY_MAP[realPlan.toLowerCase()] || realPlan).toUpperCase()} NODE]
                                </span>
                            </div>
                        </div>
                        <div className="term-md-card-border-bottom">└──────────────────────────────────────────────────────────────────────────────</div>
                    </div>

                    {/* Compute Quota & Usage Section (CLI /usage output) */}
                    <div className="term-md-section-title">## Compute Quota & Usage Diagnostics (/usage)</div>
                    <div className="term-md-card" style={{ marginBottom: '32px' }}>
                        <div className="term-md-card-border-top">┌── QUOTA ALLOCATION & REFILL METRICS ─────────────────────────────────────────</div>
                        <div className="term-md-card-content" style={{ padding: '20px' }}>
                            
                            {/* Preferred Quota Note */}
                            <div style={{ color: '#fff', fontSize: '0.9rem', marginBottom: '20px', fontFamily: 'monospace', background: 'rgba(0, 240, 255, 0.05)', padding: '10px 14px', borderRadius: '6px', border: '1px solid rgba(0, 240, 255, 0.2)' }}>
                                Preferred Quota to use: <span style={{ color: '#00F0FF', fontWeight: 'bold' }}>Regular</span> <span style={{ color: '#888' }}>(run '/quota' in CLI to change preference)</span>
                            </div>

                            {/* 5-Hour Refill Bar / Slot Quota */}
                            <div style={{ marginBottom: '22px' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                                    <span style={{ color: '#fff', fontWeight: 'bold', fontSize: '0.92rem' }}>
                                        {usageData?.is_subscribed ? `Five Hour Quota (${usageData.plan_name} Plan)` : '5-Hour Refill Quota (Free Plan)'}
                                    </span>
                                    <span style={{ color: '#00F0FF', fontWeight: 'bold', fontFamily: 'monospace' }}>
                                        {(usageData?.five_hour_quota_percent ?? usageData?.percent_remaining ?? 100).toFixed(1)}%
                                    </span>
                                </div>
                                
                                {/* Progress Bar Container */}
                                <div style={{ width: '100%', height: '12px', background: 'rgba(255,255,255,0.08)', borderRadius: '6px', overflow: 'hidden', marginBottom: '8px' }}>
                                    <div style={{
                                        width: `${Math.min(100, Math.max(0, usageData?.five_hour_quota_percent ?? usageData?.percent_remaining ?? 100))}%`,
                                        height: '100%',
                                        background: (usageData?.five_hour_quota_percent ?? 100) > 50 ? '#10b981' : (usageData?.five_hour_quota_percent ?? 100) > 20 ? '#f59e0b' : '#ef4444',
                                        borderRadius: '6px',
                                        transition: 'width 0.4s ease'
                                    }} />
                                </div>

                                <div style={{ color: '#aaa', fontSize: '0.85rem', fontFamily: 'monospace', display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
                                    {usageData?.is_subscribed ? (
                                        // Subscriber: show current slot credits remaining out of the slot allowance
                                        <>
                                            <span style={{ color: '#10b981', fontWeight: 'bold' }}>
                                                {usageData
                                                    ? `${((usageData.refill_rate ?? 0) * ((usageData.five_hour_quota_percent ?? 0) / 100)).toFixed(1)} / ${(usageData.refill_rate ?? 0).toFixed(0)} credits`
                                                    : 'Loading...'}
                                            </span>
                                            <span style={{ color: '#555' }}>•</span>
                                            <span>refills <span style={{ color: '#f9e2af', fontWeight: 'bold' }}>{usageData ? usageData.refill_rate.toFixed(0) : '—'} credits</span> in <span style={{ color: '#f9e2af', fontWeight: 'bold' }}>{formatRefillTime(usageData?.refills_in_seconds)}</span></span>
                                            <span style={{ color: '#555' }}>•</span>
                                            <span style={{ color: '#10b981' }}>unused rolls over to bank</span>
                                        </>
                                    ) : (
                                        // Free plan: show balance / cap and no-stacking note
                                        <>
                                            <span style={{ color: '#10b981', fontWeight: 'bold' }}>
                                                {usageData ? `${usageData.balance.toFixed(1)} / ${(usageData.max_limit || 100).toFixed(0)} credits` : 'Loading credits...'}
                                            </span>
                                            <span style={{ color: '#555' }}>•</span>
                                            <span>refills <span style={{ color: '#f9e2af', fontWeight: 'bold' }}>{usageData ? usageData.refill_rate.toFixed(0) : '100'} credits</span> in <span style={{ color: '#f9e2af', fontWeight: 'bold' }}>{formatRefillTime(usageData?.refills_in_seconds)}</span></span>
                                            <span style={{ color: '#555' }}>•</span>
                                            <span style={{ color: '#888' }}>no stacking</span>
                                        </>
                                    )}
                                </div>

                                {/* Free Plan Monthly Allowance Tracker */}
                                {(!usageData || !usageData.is_subscribed) && (
                                    <div style={{ color: '#888', fontSize: '0.82rem', marginTop: '8px', fontFamily: 'monospace', background: 'rgba(255,255,255,0.02)', padding: '8px 12px', borderRadius: '4px' }}>
                                        Monthly allowance remaining: <span style={{ color: '#00F0FF', fontWeight: 'bold' }}>{usageData?.free_monthly_remaining !== undefined && usageData.free_monthly_remaining >= 0 ? usageData.free_monthly_remaining.toFixed(0) : '3000'}</span> / 3000 credits
                                    </div>
                                )}
                            </div>

                            {/* Bonus Quota Bar (Via Pay As You Go) */}
                            <div style={{ marginBottom: '16px', paddingTop: '18px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                                    <span style={{ color: '#fff', fontWeight: 'bold', fontSize: '0.92rem' }}>
                                        Bonus Quota (Via Pay As You Go)
                                    </span>
                                    <span style={{ color: '#b466ff', fontWeight: 'bold', fontFamily: 'monospace' }}>
                                        {(usageData?.bonus_quota_percent ?? 0).toFixed(1)}%
                                    </span>
                                </div>

                                {/* Progress Bar Container */}
                                <div style={{ width: '100%', height: '12px', background: 'rgba(255,255,255,0.08)', borderRadius: '6px', overflow: 'hidden', marginBottom: '8px' }}>
                                    <div style={{
                                        width: `${Math.min(100, Math.max(0, usageData?.bonus_quota_percent ?? 0))}%`,
                                        height: '100%',
                                        background: (usageData?.bonus_balance ?? 0) > 0 ? 'linear-gradient(90deg, #b466ff, #00F0FF)' : '#444',
                                        borderRadius: '6px',
                                        transition: 'width 0.4s ease'
                                    }} />
                                </div>

                                <div style={{ color: '#aaa', fontSize: '0.85rem', fontFamily: 'monospace', display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
                                    <span>Credits available: <span style={{ color: '#10b981', fontWeight: 'bold' }}>{(usageData?.bonus_balance ?? 0).toFixed(1)}</span></span>
                                    <span style={{ color: '#555' }}>•</span>
                                    <span>Max Limit: <span style={{ color: '#fff', fontWeight: 'bold' }}>{(usageData?.bonus_limit ?? 0).toFixed(0)}</span></span>
                                </div>

                                <div style={{ fontSize: '0.82rem', marginTop: '8px', fontFamily: 'monospace', color: (usageData?.bonus_balance ?? 0) > 0 ? '#e5ff00' : '#888', fontWeight: (usageData?.bonus_balance ?? 0) > 0 ? 'bold' : 'normal' }}>
                                    {usageData?.is_subscribed
                                        ? ((usageData?.bonus_balance ?? 0) > 0
                                            ? '✦ Bonus credits active — consumed before your plan quota'
                                            : 'All models are included in your plan')
                                        : ((usageData?.bonus_balance ?? 0) > 0
                                            ? '✦ Premium models UNLOCKED while bonus lasts'
                                            : 'Top up via Pay As You Go below to unlock premium models')}
                                </div>
                            </div>

                            {/* Quota Bank (for Subscribers) */}
                            {usageData?.is_subscribed && (
                                <div style={{ marginTop: '16px', paddingTop: '18px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                                        <span style={{ color: '#fff', fontWeight: 'bold', fontSize: '0.92rem' }}>Quota Bank</span>
                                        <span style={{ color: '#10b981', fontWeight: 'bold', fontFamily: 'monospace' }}>
                                            {(usageData?.quota_bank_percent ?? 0).toFixed(1)}%
                                        </span>
                                    </div>
                                    {/* Bank progress bar */}
                                    <div style={{ width: '100%', height: '12px', background: 'rgba(255,255,255,0.08)', borderRadius: '6px', overflow: 'hidden', marginBottom: '8px' }}>
                                        <div style={{
                                            width: `${Math.min(100, Math.max(0, usageData?.quota_bank_percent ?? 0))}%`,
                                            height: '100%',
                                            background: (usageData?.quota_bank_percent ?? 0) > 50 ? '#10b981' : (usageData?.quota_bank_percent ?? 0) > 20 ? '#f59e0b' : '#ef4444',
                                            borderRadius: '6px',
                                            transition: 'width 0.4s ease'
                                        }} />
                                    </div>
                                    <div style={{ color: '#aaa', fontSize: '0.85rem', fontFamily: 'monospace', display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
                                        {/* balance = bank balance, max_limit = bank capacity (2× monthly) */}
                                        <span style={{ color: '#10b981', fontWeight: 'bold' }}>
                                            {usageData ? `${(usageData.balance ?? 0).toFixed(1)} / ${(usageData.max_limit ?? 0).toFixed(0)} credits` : '—'}
                                        </span>
                                        <span style={{ color: '#555' }}>•</span>
                                        <span style={{ color: '#888' }}>rolls over · stores up to 2 months capacity</span>
                                    </div>
                                    <div style={{ color: '#888', fontSize: '0.8rem', fontFamily: 'monospace', marginTop: '6px' }}>
                                        Refills processed: {usageData?.refills_processed ?? 0} / {usageData?.max_refills ?? 144}
                                    </div>
                                </div>
                            )}

                        </div>
                        <div className="term-md-card-border-bottom">└──────────────────────────────────────────────────────────────────────────────</div>
                    </div>

                    {/* Credit Top Up Component */}
                    <div style={{ marginBottom: '32px' }}>
                        <CreditTopup />
                    </div>

                    {/* Account Stats Markdown Table */}
                    <div className="term-md-section-title">## Account Diagnostics & Details</div>
                    <div className="term-md-table-wrapper" style={{ marginBottom: '32px' }}>
                        <table className="term-md-table">
                            <thead>
                                <tr>
                                    <th>METRIC / PROPERTY</th>
                                    <th>CONFIGURED VALUE</th>
                                    <th>STATUS</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td className="term-md-td-feature">Active Compute Plan</td>
                                    <td style={{ color: '#00F0FF', fontWeight: 'bold' }}>{(PLAN_DISPLAY_MAP[realPlan.toLowerCase()] || realPlan).toUpperCase()} TIER</td>
                                    <td style={{ color: '#16c60c' }}>✓ ACTIVE</td>
                                </tr>
                                <tr>
                                    <td className="term-md-td-feature">Developer Node ID</td>
                                    <td style={{ fontFamily: 'monospace', color: '#aaa' }}>{user.uid}</td>
                                    <td style={{ color: '#16c60c' }}>✓ VERIFIED</td>
                                </tr>
                                <tr>
                                    <td className="term-md-td-feature">CLI Authentication</td>
                                    <td style={{ fontFamily: 'monospace', color: '#3fb950', fontSize: '0.8rem' }}>
                                        Run <code style={{ color: '#f9e2af', background: '#0d1117', padding: '2px 6px', borderRadius: '4px' }}>/login</code> in UTIM terminal
                                    </td>
                                    <td style={{ color: '#00F0FF' }}>• DEVICE FLOW</td>
                                </tr>
                                <tr>
                                    <td className="term-md-td-feature">Registration Timestamp</td>
                                    <td style={{ color: '#888' }}>{formatDate(memberSinceDate)}</td>
                                    <td style={{ color: '#888' }}>RECORDED</td>
                                </tr>
                                <tr>
                                    <td className="term-md-td-feature">Last Session Auth</td>
                                    <td style={{ color: '#888' }}>{formatDate(lastLoginDate)}</td>
                                    <td style={{ color: '#16c60c' }}>✓ AUTHENTICATED</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    {/* Terminal Action Buttons */}
                    <div style={{ display: 'flex', gap: '16px', marginTop: '36px', paddingTop: '20px', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                        <button 
                            onClick={() => {
                                navigator.clipboard.writeText("npm install -g @emend-ai/utim");
                                alert("CLI installation command copied to clipboard!");
                            }}
                            className="term-btn-action"
                            style={{ flex: 1, cursor: 'pointer' }}
                        >
                            &gt; COPY CLI INSTALL COMMAND
                        </button>

                        <button 
                            onClick={handleLogout} 
                            className="term-btn-action"
                            style={{ padding: '12px 28px', cursor: 'pointer' }}
                        >
                            [!] TERMINATE.SESSION()
                        </button>

                        <button 
                            onClick={handleDeleteAccount} 
                            className="term-btn-danger"
                            style={{ padding: '12px 28px', cursor: 'pointer' }}
                        >
                            [X] PURGE.ACCOUNT()
                        </button>
                    </div>

                </div>
            </div>

            {isModalOpen && (
                <div className="term-modal-backdrop">
                    <div className="term-modal-box">
                        <div className="term-modal-header">[!] SYSTEM PURGE REQUIRED</div>
                        <div className="term-modal-body">
                            <p style={{ color: '#e74856', fontWeight: 'bold', margin: '0 0 10px 0' }}>
                                WARNING: THIS ACTION IS IRREVERSIBLE.
                            </p>
                            <p style={{ color: '#888', fontSize: '0.85rem', lineHeight: '1.4', margin: '0 0 20px 0' }}>
                                All compute credits, top-up histories, CLI API keys, and conversation logs will be permanently deleted.
                            </p>
                            
                            <div className="term-modal-field">
                                <label style={{ fontFamily: 'monospace' }}>CONFIRM EMAIL (Type <span style={{ color: '#00F0FF' }}>{user?.email}</span>):</label>
                                <input 
                                    type="text" 
                                    className="term-modal-input" 
                                    placeholder="Enter your email"
                                    value={emailInput}
                                    onChange={(e) => setEmailInput(e.target.value)}
                                />
                            </div>

                            {isPassword && (
                                <div className="term-modal-field" style={{ marginTop: '16px' }}>
                                    <label style={{ fontFamily: 'monospace' }}>ENTER PASSWORD:</label>
                                    <input 
                                        type="password" 
                                        className="term-modal-input" 
                                        placeholder="Enter your password"
                                        value={passwordInput}
                                        onChange={(e) => setPasswordInput(e.target.value)}
                                    />
                                </div>
                            )}

                            {isGoogle && !reauthenticated && (
                                <div style={{ marginTop: '20px' }}>
                                    <button 
                                        className="term-btn-action" 
                                        style={{ width: '100%', cursor: 'pointer', padding: '10px 0' }}
                                        onClick={async () => {
                                            setModalError('');
                                            try {
                                                const { GoogleAuthProvider, reauthenticateWithPopup } = await import('firebase/auth');
                                                const provider = new GoogleAuthProvider();
                                                await reauthenticateWithPopup(user, provider);
                                                setReauthenticated(true);
                                            } catch (authErr) {
                                                setModalError(`Verification failed: ${authErr.message}`);
                                            }
                                        }}
                                    >
                                        [G] VERIFY WITH GOOGLE POPUP
                                    </button>
                                </div>
                            )}

                            {isGoogle && reauthenticated && (
                                <p style={{ color: '#a6e3a1', fontSize: '0.85rem', marginTop: '16px', fontWeight: 'bold' }}>
                                    ✓ Google Identity Verified. Ready to delete.
                                </p>
                            )}

                            {modalError && (
                                <p style={{ color: '#e74856', fontSize: '0.85rem', marginTop: '16px', fontWeight: 'bold', lineHeight: '1.4' }}>
                                    ✗ {modalError}
                                </p>
                            )}

                            <div style={{ display: 'flex', gap: '16px', marginTop: '28px' }}>
                                <button 
                                    className="term-btn-action" 
                                    style={{ flex: 1, cursor: 'pointer', padding: '10px 0' }} 
                                    onClick={() => {
                                        setIsModalOpen(false);
                                        setEmailInput('');
                                        setPasswordInput('');
                                        setReauthenticated(false);
                                        setModalError('');
                                    }}
                                >
                                    CANCEL
                                </button>
                                <button 
                                    className="term-btn-danger" 
                                    style={{ flex: 1, cursor: 'pointer', padding: '10px 0' }}
                                    disabled={
                                        emailInput !== user?.email || 
                                        (isPassword && !passwordInput) || 
                                        (isGoogle && !reauthenticated) || 
                                        deleting
                                    }
                                    onClick={async () => {
                                        setDeleting(true);
                                        setModalError('');
                                        try {
                                            const { EmailAuthProvider, reauthenticateWithCredential } = await import('firebase/auth');
                                            
                                            if (isPassword) {
                                                const credential = EmailAuthProvider.credential(user.email, passwordInput);
                                                await reauthenticateWithCredential(user, credential);
                                            }
                                            
                                            const token = await user.getIdToken();
                                            const apiUrl = getApiUrl();
                                            
                                            // Delete user from Firebase Auth
                                            await user.delete();
                                            
                                            // Delete user from backend database
                                            try {
                                                await fetch(`${apiUrl}/api/auth/delete-me`, {
                                                    method: 'DELETE',
                                                    headers: { 'Authorization': `Bearer ${token}` }
                                                });
                                            } catch (backendErr) {
                                                console.warn('Backend cleanup deferred:', backendErr);
                                            }

                                            setIsModalOpen(false);
                                            await logout();
                                            navigate('/');
                                        } catch (err) {
                                            console.error('Failed to delete account:', err);
                                            setModalError(`Deletion failed: ${err.message || err}`);
                                        } finally {
                                            setDeleting(false);
                                        }
                                    }}
                                >
                                    {deleting ? 'EXECUTING...' : 'EXECUTE PURGE'}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ProfilePage;
