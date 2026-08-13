import React, { useState, useEffect } from 'react';
import { getApiUrl } from '../../lib/api';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import ScrollytellingHeaderNav from '../../components/ScrollytellingHeaderNav';
import ScrollytellingFooter from '../../components/ScrollytellingFooter';
import SEOHead from '../../components/SEOHead';
import CreditTopup from '../../components/CreditTopup';
import { 
  Sparkles, Check, Zap, Rocket, Shield, 
  Star, Crown, CreditCard, AlertCircle, 
  CheckCircle2, RefreshCw, HelpCircle 
} from 'lucide-react';
import '../../components/ScrollytellingMain.css';

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
  } catch (e) {}
  return false;
};

const pricingTiers = [
  {
    id: "free",
    name: "Free Plan",
    icon: Zap,
    priceMonthlyUsd: 0,
    priceMonthlyInr: 0,
    credits: "100 credits / 5 hrs",
    target: "Community developers testing UTIM with free models and 5-hour auto-refills.",
    popular: false,
    features: [
      "100 credits auto-refilled every 5 hours",
      "Up to 3,000 credits/mo allowance",
      "Free models at $0.02 in / $0.03 out per 1M",
      "Standard local workspace tools",
      "Full CLI Agent & subagent execution",
      "Stdio MCP server integration"
    ]
  },
  {
    id: "hobby",
    name: "Hobby Plan",
    icon: Rocket,
    priceMonthlyUsd: 7,
    priceMonthlyInr: 700,
    credits: "4,000 credits (+500 1st purchase bonus)",
    target: "Indie developers exploring coding MoEs and low-cost reasoning tools.",
    popular: false,
    features: [
      "4,000 monthly credits + 500 1st purchase bonus",
      "10x discount on free models ($0.002 in / $0.003 out)",
      "Coding MoEs & reasoning models",
      "Local ChromaDB semantic memory",
      "Unused credit rollover (up to 2 mos)",
      "BYOK custom provider keys",
      "Standard email support"
    ]
  },
  {
    id: "pro",
    name: "Pro Plan",
    icon: Shield,
    priceMonthlyUsd: 25,
    priceMonthlyInr: 2500,
    credits: "18,000 credits (+2,000 1st purchase bonus)",
    target: "Professional developers seeking the perfect balance of reasoning power and budget.",
    popular: true,
    features: [
      "18,000 monthly credits + 2,000 1st purchase bonus",
      "10x discount on free models ($0.002 in / $0.003 out)",
      "Full registry of premium models",
      "Priority compute allocation",
      "Unlimited MCP Stdio & SSE servers",
      "Priority developer support"
    ]
  },
  {
    id: "max",
    name: "Max Plan",
    icon: Star,
    priceMonthlyUsd: 55,
    priceMonthlyInr: 5500,
    credits: "45,000 credits (+5,000 1st purchase bonus)",
    target: "Advanced builders running heavy scrollytelling visual agents and complex structures.",
    popular: false,
    features: [
      "45,000 monthly credits + 5,000 1st purchase bonus",
      "10x discount on free models ($0.002 in / $0.003 out)",
      "Visual Analysis Engine & Image Gen",
      "Heavy model batching & subagents",
      "Custom model overrides per agent",
      "24/7 dedicated support"
    ]
  },
  {
    id: "ultimate",
    name: "Ultimate Plan",
    icon: Crown,
    priceMonthlyUsd: 110,
    priceMonthlyInr: 11000,
    credits: "90,000 credits (+12,000 1st purchase bonus)",
    target: "Elite power users utilizing ultra-premium heavy models without constraints.",
    popular: false,
    features: [
      "90,000 monthly credits + 12,000 1st purchase bonus",
      "10x discount on free models ($0.002 in / $0.003 out)",
      "Maximum priority unthrottled bandwidth",
      "Unlimited custom model overrides",
      "Team quota pooling & distribution",
      "24/7 VIP priority response"
    ]
  }
];

export default function PricingPage() {
  const { user, userProfile, getToken, refreshProfile } = useAuth();
  const navigate = useNavigate();
  const [isIndian, setIsIndian] = useState(detectIsIndian());
  const [referralInfo, setReferralInfo] = useState(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [statusMessage, setStatusMessage] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);
  const [dynamicPopularPlanId, setDynamicPopularPlanId] = useState('pro');
  const [plansList, setPlansList] = useState([]);

  useEffect(() => {
    const fetchPopularPlan = async () => {
      try {
        const apiUrl = getApiUrl();
        const res = await fetch(`${apiUrl}/api/plans`);
        if (res.ok) {
          const plans = await res.json();
          setPlansList(plans);
          const popular = plans.find(p => p.is_most_popular);
          if (popular && popular.name) {
            setDynamicPopularPlanId(popular.name.toLowerCase());
          }
        }
      } catch (err) {
        console.error('Failed to fetch popular plan details:', err);
      }
    };
    fetchPopularPlan();
  }, []);


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

  useEffect(() => {
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.async = true;
    document.body.appendChild(script);
    return () => {
      if (document.body.contains(script)) {
        document.body.removeChild(script);
      }
    };
  }, []);

  const getDiscountPct = (tierId) => {
    if (!referralInfo || !referralInfo.discounts) return 0;
    return referralInfo.discounts[tierId] || 0;
  };

  const getPriceDisplay = (tier) => {
    if (tier.priceMonthlyUsd === 0) return { main: '$0', sub: 'Forever free' };

    const discountPct = getDiscountPct(tier.id);
    const baseUsd = tier.priceMonthlyUsd;
    const baseInr = tier.priceMonthlyInr;

    if (isIndian) {
      const price = discountPct > 0 ? Math.round(baseInr * (1 - discountPct / 100)) : baseInr;
      return {
        main: `₹${price.toLocaleString()}`,
        sub: '/ month',
        original: discountPct > 0 ? `₹${baseInr.toLocaleString()}` : null,
        discountPct
      };
    } else {
      const price = discountPct > 0 ? Math.round(baseUsd * (1 - discountPct / 100)) : baseUsd;
      return {
        main: `$${price}`,
        sub: '/ month',
        original: discountPct > 0 ? `$${baseUsd}` : null,
        discountPct
      };
    }
  };

  const handleSubscribe = async (tier) => {
    if (!user) {
      navigate('/auth?redirect=/pricing');
      return;
    }

    setErrorMessage(null);
    setStatusMessage(null);

    if (tier.id === 'free') {
      setIsUpdating(true);
      setStatusMessage('Switching to Free Tier...');
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
          setStatusMessage('✓ Successfully switched to Free Tier.');
          await refreshProfile();
        } else {
          setErrorMessage(data.error || 'Failed to switch to Free Tier');
        }
      } catch (err) {
        setErrorMessage('Network error during plan switch.');
      } finally {
        setIsUpdating(false);
      }
      return;
    }

    setIsUpdating(true);
    setStatusMessage('Initializing checkout session...');

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
          plan: tier.id, 
          interval: 'monthly',
          currency: isIndian ? 'INR' : 'USD'
        })
      });
      
      const data = await response.json();
      
      if (data.success && data.subscriptionId) {
        const options = {
          key: data.keyId,
          subscription_id: data.subscriptionId,
          name: 'UTIM AI',
          description: `${tier.name} Compute Plan`,
          handler: async function (resp) {
            try {
              setStatusMessage('Verifying subscription signature...');
              const verifyRes = await fetch(`${apiUrl}/api/subscription/verify`, {
                method: 'POST',
                headers: { 
                  'Authorization': `Bearer ${token}`,
                  'Content-Type': 'application/json' 
                },
                body: JSON.stringify({
                  razorpay_subscription_id: resp.razorpay_subscription_id,
                  razorpay_payment_id: resp.razorpay_payment_id,
                  razorpay_signature: resp.razorpay_signature
                })
              });
              const verifyData = await verifyRes.json();
              if (verifyData.success) {
                setStatusMessage(`✓ Welcome to ${tier.name}! Your quota is now active.`);
                await refreshProfile();
              } else {
                setErrorMessage(verifyData.error || 'Subscription verification failed.');
              }
            } catch (err) {
              setErrorMessage('Network failure during verification.');
            } finally {
              setIsUpdating(false);
            }
          },
          prefill: {
            email: user.email || ''
          },
          theme: {
            color: '#121214'
          },
          modal: {
            ondismiss: function() {
              setIsUpdating(false);
              setStatusMessage(null);
            }
          }
        };

        const rzp = new window.Razorpay(options);
        rzp.on('payment.failed', function (resp) {
          setIsUpdating(false);
          setErrorMessage(resp.error?.description || 'Payment execution failed.');
        });
        rzp.open();
      } else {
        setErrorMessage(data.error || 'Failed to create subscription session.');
        setIsUpdating(false);
      }
    } catch (err) {
      setErrorMessage(err.message || 'Payment initiation error.');
      setIsUpdating(false);
    }
  };

  return (
    <div className="st-page-root">
      <SEOHead
        title="Compute Pricing & Plan Tiers — UTIM AI"
        description="Transparent developer compute pricing for UTIM CLI: Free ($0), Hobby ($7), Pro ($25), Max ($55), and Ultimate ($110). BYOK custom keys supported."
        canonical="https://utim.dev/pricing"
      />
      
      <ScrollytellingHeaderNav />

      <div style={{ padding: '60px 24px 100px 24px', maxWidth: 1200, margin: '0 auto' }}>
        
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <h1 style={{ fontSize: 'clamp(2.2rem, 4vw, 3.4rem)', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.02em', marginBottom: 12 }}>
            Simple, Predictable Compute Pricing
          </h1>
          <p style={{ fontSize: '1.05rem', color: 'var(--text-muted)', maxWidth: 720, margin: '0 auto', lineHeight: 1.6 }}>
            Upgrade, downgrade, or cancel anytime. All paid plans include rollover Quota Bank and priority compute.
          </p>
        </div>

        {/* Status / Error Banner */}
        {statusMessage && (
          <div style={{ background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.25)', color: '#059669', padding: '12px 16px', borderRadius: 8, fontSize: 14, marginBottom: 24, display: 'flex', alignItems: 'center', gap: 8, maxWidth: 600, margin: '0 auto 24px auto' }}>
            <CheckCircle2 size={18} />
            <span>{statusMessage}</span>
          </div>
        )}

        {errorMessage && (
          <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', color: '#DC2626', padding: '12px 16px', borderRadius: 8, fontSize: 14, marginBottom: 24, display: 'flex', alignItems: 'center', gap: 8, maxWidth: 600, margin: '0 auto 24px auto' }}>
            <AlertCircle size={18} />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Pricing Cards Grid */}
        <div className="st-pricing-grid-all">
          {pricingTiers.map((tier) => {
            const Icon = tier.icon;
            const price = getPriceDisplay(tier);
            const activePlanId = userProfile?.plan || null;
            const popularPlanId = activePlanId && activePlanId !== 'free' ? activePlanId : dynamicPopularPlanId;
            const isPopular = tier.id === popularPlanId;
            const isActivePlan = activePlanId && tier.id === activePlanId;

            return (
              <div 
                key={tier.id}
                className={`st-pricing-card ${isPopular || isActivePlan ? 'st-card-popular' : ''}`}
                style={{ display: 'flex', flexDirection: 'column' }}
              >
                {isActivePlan ? (
                  <div className="st-popular-badge" style={{ background: '#059669' }}>ACTIVE PLAN</div>
                ) : isPopular ? (
                  <div className="st-popular-badge">MOST POPULAR</div>
                ) : null}

                <div className="st-tier-icon-box">
                  <Icon size={20} />
                </div>

                <h3 className="st-tier-name">{tier.name}</h3>
                <p className="st-tier-desc">{tier.target}</p>

                <div className="st-tier-price" style={{ margin: '10px 0 8px 0' }}>
                  {price.original && (
                    <span style={{ fontSize: 13, textDecoration: 'line-through', color: 'var(--text-muted)', marginRight: 6 }}>
                      {price.original}
                    </span>
                  )}
                  <span className="st-price-val">{price.main}</span>
                  <span className="st-price-period">{price.sub}</span>
                </div>

                {price.discountPct > 0 && (
                  <div style={{ fontSize: 11.5, fontWeight: 700, color: '#059669', background: 'rgba(16,185,129,0.1)', padding: '2px 8px', borderRadius: 4, display: 'inline-block', marginBottom: 10 }}>
                    {price.discountPct}% Referral Discount Applied
                  </div>
                )}

                <div className="st-credits-tag">{tier.credits}</div>

                {(() => {
                  const serverPlan = plansList.find(p => p.name.toLowerCase() === tier.id.toLowerCase());
                  const activeCount = serverPlan ? serverPlan.active_users_count : 0;
                  if (tier.id !== 'free' && activeCount > 0) {
                    return (
                      <div className="st-active-users-count" style={{ fontSize: '11.5px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '5px', marginTop: '6px', marginBottom: '4px', fontWeight: 500 }}>
                        <span className="st-status-dot-blink" style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: '#10b981' }} />
                        <span>{activeCount.toLocaleString()} active developers</span>
                      </div>
                    );
                  }
                  return null;
                })()}

                <ul className="st-tier-features" style={{ flex: 1 }}>
                  {tier.features.map((feat, idx) => (
                    <li key={idx}>
                      <Check size={14} className="st-check" />
                      <span>{feat}</span>
                    </li>
                  ))}
                </ul>

                <button
                  onClick={() => handleSubscribe(tier)}
                  disabled={isUpdating}
                  className={`st-tier-btn ${isPopular || isActivePlan ? 'st-btn-primary' : 'st-btn-secondary'}`}
                  style={{ width: '100%', cursor: 'pointer', marginTop: 14 }}
                >
                  {tier.priceMonthlyUsd === 0 ? 'Select Free Tier' : `Subscribe to ${tier.name}`}
                </button>
              </div>
            );
          })}
        </div>

        {/* Credit Topup Refill Section */}
        <div style={{ maxWidth: 800, margin: '0 auto 48px auto' }}>
          <div style={{ textAlign: 'center', marginBottom: 20 }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: 6 }}>
              Need One-Time Compute Credits?
            </h2>
            <p style={{ fontSize: '0.92rem', color: 'var(--text-muted)' }}>
              Top-up flexible compute credits on-demand without changing your recurring subscription.
            </p>
          </div>
          <CreditTopup />
        </div>

        {/* Plan Notes */}
        <div className="st-pricing-notes-box">
          <h4 className="st-notes-title">Plan Upgrades & Payment Information</h4>
          <ul className="st-notes-list">
            <li>Users can subscribe or upgrade their plan directly from the web client UI using our integrated payment gateway.</li>
            <li>Credit consumption is calculated dynamically based on input and output tokens consumed. Free models are priced at <strong>$0.02 / 1M in and $0.03 / 1M out</strong> for Free plan users, while all Paid plan users receive a <strong>10x priority discount at $0.002 / 1M in and $0.003 / 1M out</strong>.</li>
            <li>All paid plans allow accessing the full registry of models, though recommended selections exist per plan tier to optimize credit limits.</li>
            <li>Free and paid users can also use the <strong>Bring Your Own Key (BYOK)</strong> option to connect their own custom provider keys and URLs, bypassing UTIM quota limits entirely.</li>
            <li><strong>Credit Top-Up Payments & Conversion Rates</strong>: One-time credit top-ups (ranging from $2.00 to $4,500.00) are converted dynamically to Indian Rupees (INR) using real-time market exchange rates plus a platform markup fee (varying from 2% to 5% depending on the amount). Top-up credits are added instantly to your account as bonus quota at <code>$1.00 USD = 1,000 credits</code>.</li>
          </ul>
        </div>

      </div>

      <ScrollytellingFooter />
    </div>
  );
}
