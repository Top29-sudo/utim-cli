import React, { useEffect, useState, useRef } from 'react';
import { getApiUrl } from '../../lib/api';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { updateUserProfile } from '../../lib/firebase';
import CreditTopup from '../../components/CreditTopup';
import ScrollytellingHeaderNav from '../../components/ScrollytellingHeaderNav';
import ScrollytellingFooter from '../../components/ScrollytellingFooter';
import SEOHead from '../../components/SEOHead';
import { 
  User, Shield, Zap, Terminal, LogOut, 
  Trash2, Upload, CheckCircle2, Clock, 
  Layers, CreditCard, ChevronRight, AlertTriangle 
} from 'lucide-react';
import '../../components/ScrollytellingMain.css';

const PLAN_DISPLAY_MAP = {
  free: "Free Plan",
  hobby: "Hobby Plan ($7/mo)",
  pro: "Pro Plan ($25/mo)",
  max: "Max Plan ($55/mo)",
  ultimate: "Ultimate Plan ($110/mo)"
};

export default function ProfilePage() {
  const { user, userProfile, loading, logout, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [uploading, setUploading] = useState(false);
  const [profilePic, setProfilePic] = useState(null);
  const [realPlan, setRealPlan] = useState(userProfile?.plan || 'free');
  const [usageData, setUsageData] = useState(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [modalError, setModalError] = useState('');
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      navigate('/auth');
    }
  }, [loading, isAuthenticated, navigate]);

  useEffect(() => {
    const fetchUserData = async () => {
      if (user) {
        try {
          const token = await user.getIdToken();
          const apiUrl = getApiUrl();
          
          const planRes = await fetch(`${apiUrl}/api/user-plan`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          if (planRes.ok) {
            const data = await planRes.json();
            if (data.plan) {
              setRealPlan(data.plan);
            }
          }

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

  const handleDeleteAccount = async () => {
    if (deleteConfirmation !== user.email) {
      setModalError('Please type your exact email to confirm deletion.');
      return;
    }

    setDeleting(true);
    setModalError('');
    try {
      const token = await user.getIdToken();
      const apiUrl = getApiUrl();
      const res = await fetch(`${apiUrl}/api/auth/delete-me`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        await logout();
        navigate('/');
      } else {
        const data = await res.json();
        setModalError(data.detail || 'Failed to delete account.');
      }
    } catch (err) {
      setModalError('Network error while deleting account.');
    } finally {
      setDeleting(false);
    }
  };

  if (loading || !user) {
    return (
      <div className="st-page-root">
        <ScrollytellingHeaderNav />
        <div style={{ minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ color: 'var(--text-muted)', fontSize: 15, fontWeight: 600 }}>Loading developer dashboard...</div>
        </div>
        <ScrollytellingFooter />
      </div>
    );
  }

  return (
    <div className="st-page-root">
      <SEOHead
        title="Developer Dashboard & Quota — UTIM AI"
        description="Manage your UTIM developer profile, subscription compute plan, credit balance, and CLI terminal tokens."
        canonical="https://utim.dev/profile"
      />
      
      <ScrollytellingHeaderNav />

      <div style={{ padding: '60px 24px 100px 24px', maxWidth: 1040, margin: '0 auto' }}>
        
        {/* Profile Header Card */}
        <div className="st-doc-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 24, marginBottom: 32 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
            <div style={{ position: 'relative' }}>
              <div 
                onClick={() => fileInputRef.current?.click()}
                style={{ 
                  width: 72, 
                  height: 72, 
                  borderRadius: '50%', 
                  overflow: 'hidden', 
                  background: 'var(--bg-cream-alt)', 
                  border: '2px solid var(--border-cream)', 
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                {profilePic ? (
                  <img src={profilePic} alt="Avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                ) : (
                  <User size={36} color="var(--text-muted)" />
                )}
              </div>
              <input 
                type="file" 
                ref={fileInputRef} 
                onChange={handleFileChange} 
                accept="image/*" 
                style={{ display: 'none' }} 
              />
            </div>

            <div>
              <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: 4 }}>
                {user.displayName || userProfile?.displayName || 'Developer'}
              </h1>
              <p style={{ fontSize: '0.92rem', color: 'var(--text-muted)' }}>
                {user.email}
              </p>
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <span className="st-tag-item st-tag-dark">
                  {PLAN_DISPLAY_MAP[realPlan] || realPlan.toUpperCase()}
                </span>
                <span className="st-tag-item">
                  ✓ Verified Account
                </span>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 12 }}>
            <Link to="/pricing" className="st-nav-primary-btn" style={{ padding: '8px 18px', fontSize: 13.5 }}>
              Upgrade Plan
            </Link>
            <button 
              onClick={handleLogout}
              className="st-btn-secondary"
              style={{ padding: '8px 18px', fontSize: 13.5, borderRadius: 8, display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <LogOut size={15} />
              <span>Log Out</span>
            </button>
          </div>
        </div>

        {/* Dashboard Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(320px, 100%), 1fr))', gap: 28 }}>
          
          {/* Card 1: Subscription & Quota Progress Bars */}
          <div className="st-doc-card">
            <h2 className="st-doc-card-title" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Zap size={20} /> Compute Allowance & Quota
              </span>
              <span className="st-tag-item st-tag-dark" style={{ fontSize: 11 }}>
                {PLAN_DISPLAY_MAP[realPlan] || realPlan.toUpperCase()}
              </span>
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 18 }}>
              {/* Bar 1: 5-Hour Cycle Slot Quota */}
              <div style={{ background: 'var(--bg-cream-alt)', borderRadius: 10, padding: '14px 16px', border: '1px solid var(--border-cream)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, fontSize: 13 }}>
                  <span style={{ fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                    ⚡ 5-Hour Refill Slot
                  </span>
                  <span style={{ fontWeight: 800, color: '#059669', fontSize: 12 }}>
                    {usageData?.five_hour_quota_percent ?? 100}% Remaining
                  </span>
                </div>
                <div style={{ height: 8, width: '100%', background: '#E2E8F0', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ 
                    height: '100%', 
                    width: `${usageData?.five_hour_quota_percent ?? 100}%`, 
                    background: 'linear-gradient(90deg, #10B981, #059669)', 
                    borderRadius: 4, 
                    transition: 'width 0.6s ease' 
                  }} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>
                  <span>Slot Rate: {usageData?.refill_rate || 100} credits / 5 hrs</span>
                  <span>Auto-Refills Active</span>
                </div>
              </div>

              {/* Bar 2: Rollover Quota Bank */}
              <div style={{ background: 'var(--bg-cream-alt)', borderRadius: 10, padding: '14px 16px', border: '1px solid var(--border-cream)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, fontSize: 13 }}>
                  <span style={{ fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                    🏦 Rollover Quota Bank
                  </span>
                  <span style={{ fontWeight: 800, color: 'var(--text-primary)', fontSize: 12 }}>
                    {(usageData?.balance || 0).toLocaleString()} / {(usageData?.max_limit || 100).toLocaleString()} Credits
                  </span>
                </div>
                <div style={{ height: 8, width: '100%', background: '#E2E8F0', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ 
                    height: '100%', 
                    width: `${usageData?.quota_bank_percent ?? (realPlan === 'free' ? 100 : 0)}%`, 
                    background: 'var(--accent-black)', 
                    borderRadius: 4, 
                    transition: 'width 0.6s ease' 
                  }} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>
                  <span>Plan Credit Balance</span>
                  <span>{usageData?.quota_bank_percent ?? 100}% Available</span>
                </div>
              </div>

              {/* Bar 3: Bonus Quota */}
              <div style={{ background: 'var(--bg-cream-alt)', borderRadius: 10, padding: '14px 16px', border: '1px solid var(--border-cream)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, fontSize: 13 }}>
                  <span style={{ fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                    🎁 Bonus Quota
                  </span>
                  <span style={{ fontWeight: 800, color: '#6366F1', fontSize: 12 }}>
                    {(usageData?.bonus_balance || 0).toLocaleString()} / {(usageData?.bonus_limit || 20000).toLocaleString()} Bonus Credits
                  </span>
                </div>
                <div style={{ height: 8, width: '100%', background: '#E2E8F0', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ 
                    height: '100%', 
                    width: `${usageData?.bonus_quota_percent ?? 0}%`, 
                    background: 'linear-gradient(90deg, #818CF8, #4F46E5)', 
                    borderRadius: 4, 
                    transition: 'width 0.6s ease' 
                  }} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>
                  <span>Bonus & Top-up Credits (Non-expiring)</span>
                  <span>{usageData?.bonus_quota_percent ?? 0}% Remaining</span>
                </div>
              </div>
            </div>
            
            <div style={{ marginTop: 20 }}>
              <Link to="/pricing" style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--text-primary)', textDecoration: 'underline' }}>
                View Plan Comparison & Allowances →
              </Link>
            </div>
          </div>

          {/* Card 2: CLI Pairing & Terminal Login */}
          <div className="st-doc-card">
            <h2 className="st-doc-card-title">
              <Terminal size={20} /> Terminal Pair & CLI Login
            </h2>
            <p style={{ fontSize: '0.92rem', color: 'var(--text-body)', lineHeight: 1.6, marginBottom: 14 }}>
              To connect your local workstation terminal with your cloud subscription quota:
            </p>
            <div className="st-code-block" style={{ marginBottom: 14 }}>
              <div>utim login</div>
              <div style={{ color: '#94a3b8' }}># Or run /activate from terminal</div>
            </div>
            <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
              Your browser will open an 8-character verification screen to pair your local machine securely with 0 token leakage.
            </p>
            <div style={{ marginTop: 16 }}>
              <Link to="/activate" className="st-btn-secondary" style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <span>Open Device Activation</span>
                <ChevronRight size={14} />
              </Link>
            </div>
          </div>

        </div>

        {/* Real Credit Topup Refill Section */}
        <CreditTopup />

        {/* Danger Zone: Delete Account */}
        <div className="st-doc-card" style={{ marginTop: 32, border: '1px solid rgba(239,68,68,0.3)', background: '#FFF5F5' }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#DC2626', display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <AlertTriangle size={18} /> Danger Zone
          </h2>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-body)', marginBottom: 16 }}>
            Permanently delete your developer identity, usage history, and cancel active subscription compute allocations.
          </p>
          <button
            onClick={() => setIsDeleteModalOpen(true)}
            style={{ background: '#DC2626', color: '#FFFFFF', border: 'none', padding: '9px 18px', borderRadius: 8, fontSize: 13.5, fontWeight: 700, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            <Trash2 size={15} />
            <span>Delete Account</span>
          </button>
        </div>

      </div>

      {/* Delete Confirmation Modal */}
      {isDeleteModalOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999, padding: 20 }}>
          <div style={{ background: '#FFFFFF', borderRadius: 16, maxWidth: 440, width: '100%', padding: 28, boxShadow: 'var(--shadow-xl)', border: '1px solid var(--border-cream)' }}>
            <h3 style={{ fontSize: '1.3rem', fontWeight: 800, color: '#DC2626', marginBottom: 8 }}>
              Confirm Account Deletion
            </h3>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-body)', lineHeight: 1.5, marginBottom: 16 }}>
              This action cannot be undone. Please type your email <strong>{user.email}</strong> to permanently erase your profile:
            </p>
            <input
              type="text"
              placeholder={user.email}
              value={deleteConfirmation}
              onChange={(e) => setDeleteConfirmation(e.target.value)}
              style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border-cream)', marginBottom: 14, fontSize: 14, outline: 'none' }}
            />
            {modalError && (
              <div style={{ color: '#DC2626', fontSize: 13, marginBottom: 12 }}>
                {modalError}
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button
                onClick={() => setIsDeleteModalOpen(false)}
                className="st-btn-secondary"
                style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13.5 }}
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteAccount}
                disabled={deleting}
                style={{ background: '#DC2626', color: '#FFFFFF', border: 'none', padding: '8px 16px', borderRadius: 8, fontSize: 13.5, fontWeight: 700, cursor: 'pointer' }}
              >
                {deleting ? 'Deleting...' : 'Delete Permanently'}
              </button>
            </div>
          </div>
        </div>
      )}

      <ScrollytellingFooter />
    </div>
  );
}
