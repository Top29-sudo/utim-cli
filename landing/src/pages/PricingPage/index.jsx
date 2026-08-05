import React, { useState, useEffect } from 'react';
import { getApiUrl } from '../../lib/api';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import '../../components/PowershellUI/PowershellUI.css';
import CreditTopup from '../../components/CreditTopup';

const detectIsIndian = () => {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (tz && (tz.toLowerCase().includes('kolkata') || tz.toLowerCase().includes('calcutta'))) {
      return true;
    }
    const locale = navigator.language || '';
    if (locale.toLowerCase().includes('-in')) {
      return true;
    }
    if (navigator.languages && navigator.languages.some(l => l.toLowerCase().includes('-in'))) {
      return true;
    }
  } catch (e) {}
  return false;
};

const pricingTiers = [
  {
    id: "free",
    name: "Free Node",
    price: "$0",
    period: "mo",
    cores: "Standard Compute (Low Priority)",
    limits: "100 Credits (Refilled every 5 hours)",
    features: [
      "Capped at 3,000 monthly credits with no quota bank (no stacking)",
      "Access to Free-tier models only (cohere/north-mini-code, nvidia/nemotron-nano, qwen3-coder)",
      "Standard local workspace tools (file editing, command execution)",
      "Standard ChromaDB semantic memory database",
      "Community support (Discord)"
    ],
    color: "#888888"
  },
  {
    id: "hobby",
    name: "Hobbyist Node",
    price: "$7",
    period: "mo",
    cores: "Personal Compute (Normal Priority)",
    limits: "4,000 Monthly Credits (+500 bonus credits on first purchase)",
    features: [
      "Access to Hobby-tier MoEs & reasoning (deepseek-r1, kimi-k2.7-code, minimax-m3)",
      "Full local semantic experiences database & cross-folder auto-sync",
      "Unused credit rollover allowed for up to 2 months",
      "Standard email support (within 48 hours)"
    ],
    color: "#ec4899"
  },
  {
    id: "starter",
    name: "Starter Node",
    price: "$25",
    period: "mo",
    cores: "Dedicated Compute (High Priority)",
    limits: "18,000 Monthly Credits (+2,000 bonus credits on first purchase)",
    features: [
      "Access to Pro-tier elite reasoning (claude-sonnet-4.6, gpt-5.4, gemini-3.5-flash)",
      "Fully supports custom Model Context Protocol (MCP) server registries",
      "Share Chat & Zip exports for up to 5 project workspaces (1-month link retention)",
      "Standard developer support SLA (within 24 hours)"
    ],
    color: "#00F0FF"
  },
  {
    id: "professional",
    name: "Professional Core",
    price: "$55",
    period: "mo",
    cores: "Architecture Lock (Top Priority)",
    limits: "45,000 Monthly Credits (+5,000 bonus credits on first purchase)",
    features: [
      "Access to all model tiers (including gpt-5.3-codex, claude-opus-4.6, claude-fable-5)",
      "Share Chat & Zip exports for up to 20 project workspaces (6-month link retention)",
      "Mini-agents orchestration, custom workspace rules, & UI buttons integration",
      "Priority developer support SLA (within 12 hours)"
    ],
    color: "#e8c97a"
  },
  {
    id: "ultimate",
    name: "MAX Node",
    price: "$110",
    period: "mo",
    cores: "Quantum Cluster (Instant Execution)",
    limits: "90,000 Monthly Credits (+12,000 bonus credits on first purchase)",
    features: [
      "Access to all models with maximum throughput limits",
      "Unlimited project zip exports & lifetime storage retention",
      "Unlimited local vector memory database",
      "Elite cognitive testing, layout-visual QA, and multi-agent regression loops",
      "Premium 24/7 dedicated engineering support SLA (within 1 hour)"
    ],
    color: "#00FF66"
  },
  {
    id: "payg",
    name: "Pay As You Go",
    price: "Top-up",
    period: "one-time",
    cores: "Flexible Credit Purchases",
    limits: "1,000 credits = $1.00 USD",
    features: [
      "No recurring monthly subscription fees",
      "Topped-up credits are added directly to your bonus quota bank",
      "Full access to the model registry and advanced local workspace tools",
      "Pay securely via card, netbanking, or UPI payments"
    ],
    color: "#ffc107"
  }
];

const PricingPage = () => {
  const { user, getToken, refreshProfile } = useAuth();
  const location = useLocation();
  const [tierIndex, setTierIndex] = useState(3); // Default to Professional
  const [billingPeriod, setBillingPeriod] = useState('monthly'); // 'monthly' or 'yearly'
  const [isUpdating, setIsUpdating] = useState(false);
  const [message, setMessage] = useState('');
  const currentTier = pricingTiers[tierIndex];
  const navigate = useNavigate();
  const [isIndian, setIsIndian] = useState(detectIsIndian());
  const [referralInfo, setReferralInfo] = useState(null);

  useEffect(() => {
    if (user) {
      const fetchReferralInfo = async () => {
        try {
          const token = await getToken();
          const apiUrl = getApiUrl();
          const res = await fetch(`${apiUrl}/api/referrals/info`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          const data = await res.json();
          if (data && data.discounts) {
            setReferralInfo(data);
          }
        } catch (err) {
          console.error('Failed to fetch referral info:', err);
        }
      };
      fetchReferralInfo();
    }
  }, [user]);

  const getDiscountPct = (tierId) => {
    if (!referralInfo || !referralInfo.discounts) return 0;
    let dbPlanId = tierId;
    if (tierId === 'starter') dbPlanId = 'pro';
    if (tierId === 'professional') dbPlanId = 'max';
    return referralInfo.discounts[dbPlanId] || 0;
  };

  const getDisplayPrice = (tier) => {
    if (tier.id === 'free') return '$0';
    if (tier.id === 'payg') return 'Top-up';
    
    const discountPct = getDiscountPct(tier.id);
    
    if (isIndian) {
      const inrPrices = {
        hobby: 700,
        starter: 2500,
        professional: 5500,
        ultimate: 11000
      };
      const basePrice = inrPrices[tier.id] || 0;
      if (discountPct > 0) {
        const discountedPrice = Math.round(basePrice * (1 - discountPct / 100));
        return {
          price: `Rs. ${discountedPrice}/mo`,
          original: `Rs. ${basePrice}/mo`,
          discount: discountPct
        };
      }
      return `Rs. ${basePrice}/mo`;
    } else {
      const usdPrices = {
        hobby: 7,
        starter: 25,
        professional: 55,
        ultimate: 110
      };
      const basePrice = usdPrices[tier.id] || 0;
      if (discountPct > 0) {
        const discountedPrice = Math.round(basePrice * (1 - discountPct / 100));
        return {
          price: `$${discountedPrice}/mo`,
          original: `$${basePrice}/mo`,
          discount: discountPct
        };
      }
      return `${tier.price}/mo`;
    }
  };

  const renderPrice = (tier) => {
    const data = getDisplayPrice(tier);
    if (typeof data === 'string') {
      return <span>{data}</span>;
    }
    if (data.original) {
      return (
        <span style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center' }}>
          <span style={{ fontSize: '0.8rem', color: '#777', textDecoration: 'line-through' }}>
            {data.original}
          </span>
          <span style={{ color: tier.color || '#fff' }}>
            {data.price}
          </span>
          <span style={{ fontSize: '0.7rem', color: '#00FF66', background: 'rgba(0, 255, 102, 0.1)', padding: '2px 6px', borderRadius: '4px', marginTop: '4px', display: 'inline-block' }}>
            {data.discount}% OFF (Referrals)
          </span>
        </span>
      );
    }
    return <span>{data.price}</span>;
  };

  // Dynamically detect user country via GeoIP with timezone fallback
  useEffect(() => {
    fetch('https://ipapi.co/json/')
      .then(res => res.json())
      .then(data => {
        if (data && data.country_code) {
          setIsIndian(data.country_code === 'IN');
        }
      })
      .catch(() => {
        // Keeps the default timezone/locale detection state if GeoIP fetch is blocked
      });
  }, []);

  const getSavingsText = (tier) => {
    return null;
  };

  // Parse plan from query param on mount
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const planParam = params.get('plan');
    if (planParam) {
      const idx = pricingTiers.findIndex(t => t.id === planParam);
      if (idx !== -1) {
        setTierIndex(idx);
      }
    }
  }, [location.search]);

  // Primary admin account for quick switching
  const isAdmin = user && user.uid === 'WOCbb9RlPwgmIpi1dM7gv80gPHu2';

  // Dynamically load Razorpay SDK
  useEffect(() => {
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.async = true;
    document.body.appendChild(script);
    
    return () => {
      document.body.removeChild(script);
    };
  }, []);

  const handlePurchase = async () => {
    if (!user) {
      navigate('/auth?callback=/pricing-checkout');
      return;
    }

    if (currentTier.id === 'free') {
      setIsUpdating(true);
      setMessage('Switching compute node to Free Tier...');
      try {
        const token = await getToken();
        const apiUrl = getApiUrl();
        const response = await fetch(`${apiUrl}/api/user-plan`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ plan: 'free' })
        });
        const data = await response.json();
        if (data.success) {
          setMessage('SUCCESS: Node reconfigured to Free Tier');
          await refreshProfile();
        } else {
          setMessage(`ERROR: ${data.error || 'Failed to switch to Free Tier'}`);
        }
      } catch (err) {
        setMessage('ERROR: Network failure during reconfiguration');
      } finally {
        setIsUpdating(false);
      }
      return;
    }

    setIsUpdating(true);
    setMessage('Initializing secure subscription channel...');

    try {
      const token = await getToken();
      const apiUrl = getApiUrl();
      
      const response = await fetch(`${apiUrl}/api/subscription/create`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ 
          plan: currentTier.id, 
          interval: 'monthly',
          currency: isIndian ? 'INR' : 'USD'
        })
      });
      
      const data = await response.json();
      
      if (data.success && data.subscriptionId) {
        const options = {
          key: data.keyId,
          subscription_id: data.subscriptionId,
          name: 'U.T.I.M AI',
          description: `${currentTier.name} Subscription (Autopay)`,
          handler: async function (response) {
            try {
              setMessage('Verifying subscription signature...');
              const verifyRes = await fetch(`${apiUrl}/api/subscription/verify`, {
                method: 'POST',
                headers: { 
                  'Authorization': `Bearer ${token}`,
                  'Content-Type': 'application/json' 
                },
                body: JSON.stringify({
                  razorpay_subscription_id: response.razorpay_subscription_id,
                  razorpay_payment_id: response.razorpay_payment_id,
                  razorpay_signature: response.razorpay_signature
                })
              });
              const verifyData = await verifyRes.json();
              if (verifyData.success) {
                setMessage(`SUCCESS: Node reconfigured to ${currentTier.name} (Autopay Active)`);
                // Update profile state instantly
                await refreshProfile();
              } else {
                setMessage(`ERROR: ${verifyData.error || 'Subscription verification failed'}`);
              }
            } catch (err) {
              setMessage('ERROR: Network failure during verification');
            } finally {
              setIsUpdating(false);
            }
          },
          prefill: {
            email: user.email || ''
          },
          theme: {
            color: '#00f0ff'
          },
          modal: {
            ondismiss: function() {
              setIsUpdating(false);
              setMessage('Checkout cancelled');
            }
          }
        };

        const rzp = new window.Razorpay(options);
        rzp.on('payment.failed', function (response) {
          setIsUpdating(false);
          setMessage('ERROR: ' + (response.error.description || 'Payment failed'));
        });
        rzp.open();
      } else {
        setMessage(`ERROR: ${data.error || 'Failed to initialize subscription'}`);
        setIsUpdating(false);
      }
    } catch (err) {
      console.error('Purchase error:', err);
      setMessage('ERROR: Network failure during checkout');
      setIsUpdating(false);
    }
  };

  const handleAdminSwitch = async () => {
    if (!isAdmin) return;
    
    setIsUpdating(true);
    setMessage('');
    
    try {
      const token = await getToken();
      const apiUrl = getApiUrl();
      
      const response = await fetch(`${apiUrl}/api/user-plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ plan: currentTier.id })
      });
      
      const data = await response.json();
      if (data.success) {
        setMessage(`SUCCESS: Node reconfigured to ${currentTier.name}`);
        // Update profile state instantly
        await refreshProfile();
      } else {
        setMessage(`ERROR: ${data.error || 'Failed to switch'}`);
      }
    } catch (err) {
      console.error('Admin switch error:', err);
      setMessage('ERROR: Network failure during reconfiguration');
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="term-wrapper">
      <div className="term-window">
        {/* Title / Tab Bar */}
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
          <div className="term-tab active">
            <span className="term-tab-icon" style={{color: '#e8c97a'}}>$</span>
            <span className="term-tab-title">Billing Checkout</span>
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
          <div className="term-tab-add">+</div>
          <div className="term-tab-chevron">v</div>
          <div className="term-window-controls">
            <div className="term-ctrl">_</div>
            <div className="term-ctrl">□</div>
            <div className="term-ctrl close" onClick={() => navigate('/')}>×</div>
          </div>
        </div>

        {/* Content Area */}
        <div className="term-content term-markdown-view" style={{ padding: '32px' }}>
          {/* Header Block */}
          <div className="term-md-header" style={{ marginBottom: '24px' }}>
            <div className="term-md-tag">[SECURE BILLING CHANNEL]</div>
            <h1 className="term-md-title" style={{ fontSize: '1.6rem', margin: '8px 0' }}>
              # Compute Node Subscription Reconfiguration
            </h1>
            <div className="term-md-subtitle" style={{ color: '#fff', fontSize: '0.9rem' }}>
              Select target tier below to adjust and re-route your agent compute infrastructure.
            </div>
          </div>

          <div className="term-md-divider">================================================================================</div>

          {/* Promotional Notice */}
          <div className="term-md-card" style={{ marginBottom: '24px', borderColor: '#E5FF00', background: 'rgba(229, 255, 0, 0.02)' }}>
            <div style={{ color: '#E5FF00', fontWeight: 'bold', fontSize: '0.85rem', fontFamily: 'monospace', padding: '12px 16px', borderBottom: '1px solid rgba(229, 255, 0, 0.1)' }}>
              [PROMOTIONAL SYSTEM NOTICE • TEMPORARY ACCESS GRANTED]
            </div>
            <div style={{ padding: '14px 16px', color: '#ccc', fontSize: '0.85rem', lineHeight: '1.5', fontFamily: 'monospace' }}>
              All advanced tools (<strong>Image Generation</strong>, <strong>Blender Agent</strong>, <strong>Web Search Agent</strong>, <strong>Synthetic Eye</strong> for non-vision models, and <strong>Planning Agent</strong>) along with the global <strong>Experience Vector Database</strong> are currently <strong>FREE</strong> for all subscription tiers until June end (Extended through July end!).
            </div>
          </div>

          {/* Referral Discount Notice */}
          {referralInfo && Object.keys(referralInfo.discounts || {}).length > 0 && (
            <div className="term-md-card" style={{ marginBottom: '24px', borderColor: 'rgba(0,255,102,0.3)', background: 'rgba(0,255,102,0.04)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px' }}>
                <div>
                  <div style={{ color: '#00FF66', fontWeight: 'bold', fontSize: '0.85rem', fontFamily: 'monospace', marginBottom: '4px' }}>
                    [REFERRAL DISCOUNTS ACTIVE]
                  </div>
                  <div style={{ color: '#aaa', fontSize: '0.8rem' }}>
                    You have earned referral discounts on {Object.keys(referralInfo.discounts).length} plan(s). Prices shown below reflect your discounts.
                  </div>
                </div>
                <button
                  className="term-btn-action"
                  style={{ fontSize: '0.78rem', padding: '6px 12px', borderColor: 'rgba(0,255,102,0.3)', color: '#00FF66', whiteSpace: 'nowrap' }}
                  onClick={() => navigate('/referral')}
                >
                  &gt; VIEW_REFERRALS()
                </button>
              </div>
            </div>
          )}

          {!referralInfo && user && (
            <div style={{ textAlign: 'right', marginBottom: '12px' }}>
              <button
                className="term-btn-action"
                style={{ fontSize: '0.78rem', padding: '6px 12px', borderColor: 'rgba(0,255,102,0.2)', color: '#00FF66' }}
                onClick={() => navigate('/referral')}
              >
                % Earn Free Access via Referrals
              </button>
            </div>
          )}

          {/* Billing Cycle Toggle */}


          {/* Tier Grid Selector */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '12px', marginBottom: '24px' }} className="tw-pricing-select-grid">
            {pricingTiers.map((tier, idx) => (
              <div 
                key={tier.id}
                onClick={() => { setTierIndex(idx); setMessage(''); }}
                style={{
                  border: tierIndex === idx ? `1px solid ${tier.color}` : '1px solid rgba(255,255,255,0.06)',
                  background: tierIndex === idx ? 'rgba(255,255,255,0.02)' : 'transparent',
                  padding: '16px',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  textAlign: 'center'
                }}
              >
                <div style={{ color: tierIndex === idx ? '#fff' : '#ccc', fontSize: '0.85rem', fontWeight: 'bold' }}>
                  {tier.name}
                </div>
                <div style={{ color: tierIndex === idx ? tier.color : '#888', fontSize: '0.9rem', fontWeight: 'bold', marginTop: '6px', fontFamily: 'monospace', wordBreak: 'break-all' }}>
                  {renderPrice(tier)}
                </div>
              </div>
            ))}
          </div>

          {/* Detailed Readout / Confirm Card */}
          {currentTier.id === 'payg' ? (
            <div style={{ marginBottom: '28px' }}>
              <CreditTopup />
            </div>
          ) : (
            <div className="term-md-card" style={{ marginBottom: '28px' }}>
              <div className="term-md-card-border-top">┌── RECONFIGURATION TARGET: {currentTier.name.toUpperCase()} ─────────────────────────────</div>
              <div className="term-md-card-content" style={{ padding: '16px 20px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }} className="tw-pricing-select-grid">
                  <div>
                    <div style={{ color: '#fff', fontSize: '0.75rem', fontWeight: 'bold' }}>COMPUTE ALLOCATION</div>
                    <div style={{ color: '#fff', fontFamily: 'monospace', fontSize: '0.95rem' }}>{currentTier.cores}</div>
                  </div>
                  <div>
                    <div style={{ color: '#fff', fontSize: '0.75rem', fontWeight: 'bold' }}>THROUGHPUT RATIO</div>
                    <div style={{ color: currentTier.color, fontFamily: 'monospace', fontSize: '0.95rem', fontWeight: 'bold' }}>{currentTier.limits}</div>
                  </div>
                </div>
                
                <div style={{ color: '#fff', fontSize: '0.75rem', fontWeight: 'bold', marginBottom: '8px' }}>INCLUDED DIRECTIVES</div>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {currentTier.features.map((feat, i) => {
                    const isCredits = feat.toLowerCase().includes('credits');
                    return (
                      <li 
                        key={i} 
                        style={{ 
                          fontSize: '0.85rem', 
                          color: isCredits ? (currentTier.color || '#00f0ff') : '#fff', 
                          fontWeight: isCredits ? 'bold' : 'normal',
                          display: 'flex', 
                          gap: '8px' 
                        }}
                      >
                        <span style={{ color: currentTier.color }}>[OK]</span>
                        <span>{feat}</span>
                      </li>
                    );
                  })}
                </ul>

                <div className="term-md-divider" style={{ margin: '14px 0' }}>---------------------------------------------------------</div>

                <div style={{ display: 'flex', justifycontent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ color: '#fff', fontSize: '0.75rem', fontWeight: 'bold' }}>MONTHLY LICENSE FEE</div>
                    <div style={{ color: '#00F0FF', fontSize: '1.2rem', fontWeight: 'bold', fontFamily: 'monospace' }}>
                      {renderPrice(currentTier)}
                    </div>
                    {billingPeriod === 'yearly' && currentTier.id !== 'free' && (
                      <div style={{ color: '#00FF66', fontSize: '0.75rem', marginTop: '4px', fontFamily: 'monospace' }}>
                        {getSavingsText(currentTier)}
                      </div>
                    )}
                  </div>
                  <div>
                    {isAdmin ? (
                      <button 
                        onClick={handleAdminSwitch}
                        disabled={isUpdating}
                        className="term-btn-action"
                        style={{ borderColor: 'rgba(0, 240, 255, 0.4)', color: '#00F0FF' }}
                      >
                        {isUpdating ? 'SYNCHRONIZING...' : '> ADMIN_RECONFIGURE()'}
                      </button>
                    ) : (
                      <button 
                        onClick={handlePurchase}
                        disabled={isUpdating}
                        className="term-btn-action"
                        style={{ borderColor: 'rgba(0, 240, 255, 0.4)', color: '#00F0FF' }}
                      >
                        {isUpdating ? 'SYNCHRONIZING...' : '> INITIALIZE_RECONFIG()'}
                      </button>
                    )}
                  </div>
                </div>
              </div>
              <div className="term-md-card-border-bottom">└──────────────────────────────────────────────────────────────────────────────</div>
            </div>
          )}

          {/* Feedback Messages */}
          {message && (
            <div style={{ 
              background: message.startsWith('ERROR') ? 'rgba(231, 72, 86, 0.1)' : 'rgba(39, 201, 63, 0.1)',
              border: message.startsWith('ERROR') ? '1px solid rgba(231, 72, 86, 0.3)' : '1px solid rgba(39, 201, 63, 0.3)',
              color: message.startsWith('ERROR') ? '#e74856' : '#27c93f',
              padding: '12px',
              borderRadius: '6px',
              fontSize: '0.88rem',
              marginBottom: '16px',
              fontFamily: 'monospace'
            }}>
              {message}
            </div>
          )}

          <p style={{ color: '#fff', fontSize: '0.75rem', textAlign: 'center', marginTop: '16px' }}>
            No credit card required for Free Node.
          </p>
          <div style={{ 
            color: '#fff', 
            fontSize: '0.72rem', 
            textAlign: 'center', 
            marginTop: '16px', 
            borderTop: '1px solid rgba(255,255,255,0.04)', 
            paddingTop: '8px',
            fontFamily: 'monospace',
            lineHeight: '1.4'
          }}>
            [SYSTEM NOTE] Rollover quota & degradation mechanism: When a user buys 2 Pro plans and saves up quota, then degrades to a Hobby plan, they retain $7 in the active Hobby quota bank; the remaining $23 is converted to bonus credits at a 50% conversion rate. Topped-up credits via pay-as-you-go are added directly to your bonus quota.
          </div>

        </div>
      </div>
    </div>
  );
};

export default PricingPage;
