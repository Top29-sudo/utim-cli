import React, { useState, useEffect } from 'react';
import { Check, Sparkles, Zap, Rocket, Shield, Star, Crown } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getApiUrl } from '../lib/api';

export default function ScrollytellingPricing() {
  const { userProfile } = useAuth();
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
  
  // Dynamic Popularity: highlights user's active paid plan or defaults to the db-most-active plan
  const activePlanId = userProfile?.plan || null;
  const popularPlanId = activePlanId && activePlanId !== 'free' ? activePlanId : dynamicPopularPlanId;

  // All 5 plans in ascending order of price
  const allTiers = [
    {
      id: "free",
      name: "Free Plan",
      icon: Zap,
      priceMonthly: 0,
      credits: "100 credits / 5 hrs",
      target: "Community developers testing UTIM with free models and 5-hour auto-refills.",
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
      priceMonthly: 7,
      credits: "4,000 credits (+500 1st purchase bonus)",
      target: "Indie developers exploring coding MoEs and low-cost reasoning tools.",
      features: [
        "4,000 monthly credits + 500 1st purchase bonus",
        "10x discount on free models ($0.002 in / $0.003 out)",
        "Coding MoEs & reasoning models",
        "Local ChromaDB semantic memory",
        "Unused credit rollover (up to 2 mos)",
        "BYOK custom provider keys"
      ]
    },
    {
      id: "pro",
      name: "Pro Plan",
      icon: Shield,
      priceMonthly: 25,
      credits: "18,000 credits (+2,000 1st purchase bonus)",
      target: "Professional developers seeking the perfect balance of reasoning power and budget.",
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
      priceMonthly: 55,
      credits: "45,000 credits (+5,000 1st purchase bonus)",
      target: "Advanced builders running heavy scrollytelling visual agents and complex structures.",
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
      priceMonthly: 110,
      credits: "90,000 credits (+12,000 1st purchase bonus)",
      target: "Elite power users utilizing ultra-premium heavy models without constraints.",
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

  const renderCard = (tier) => {
    const IconComponent = tier.icon;
    const price = tier.priceMonthly;
    const isPopular = tier.id === popularPlanId;
    const isActivePlan = activePlanId && tier.id === activePlanId;

    return (
      <div 
        key={tier.id} 
        className={`st-pricing-card ${isPopular || isActivePlan ? 'st-card-popular' : ''}`}
      >
        {isActivePlan ? (
          <div className="st-popular-badge" style={{ background: '#059669' }}>ACTIVE PLAN</div>
        ) : isPopular ? (
          <div className="st-popular-badge">MOST POPULAR</div>
        ) : null}
        
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div className="st-tier-icon-box" style={{ marginBottom: 0 }}>
            <IconComponent size={20} />
          </div>
        </div>
        
        <h3 className="st-tier-name">{tier.name}</h3>
        <p className="st-tier-desc">{tier.target}</p>
        
        <div className="st-tier-price">
          <span className="st-price-val">${price}</span>
          <span className="st-price-period">/ mo</span>
        </div>
        
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

        <ul className="st-tier-features">
          {tier.features.map((feat, fIdx) => (
            <li key={fIdx}>
              <Check size={14} className="st-check" />
              <span>{feat}</span>
            </li>
          ))}
        </ul>

        <Link 
          to="/auth" 
          className={`st-tier-btn ${isPopular || isActivePlan ? 'st-btn-primary' : 'st-btn-secondary'}`}
        >
          {tier.priceMonthly === 0 ? "Get Started Free" : `Subscribe to ${tier.name}`}
        </Link>
      </div>
    );
  };

  return (
    <section className="st-pricing-section" id="pricing">
      <div className="st-container">
        {/* Section Header */}
        <div className="st-section-header">
          <h2 className="st-section-title">
            Flexible Compute Node Plans
          </h2>
          <p className="st-section-subtitle">
            UTIM offers several flexible compute node plan tiers tailored to different developer workflows and credit consumption needs.
          </p>
        </div>

        {/* All 5 Plan Cards Side-by-Side */}
        <div className="st-pricing-grid-all">
          {allTiers.map(renderCard)}
        </div>

        {/* Plan Upgrades & Payment Notes from pricing.md */}
        <div className="st-pricing-notes-box">
          <h4 className="st-notes-title">Plan Upgrades & Payment Information</h4>
          <ul className="st-notes-list">
            <li>Users can subscribe or upgrade their plan directly from the web client UI (profile page) using our integrated payment gateway.</li>
            <li>Credit consumption is calculated dynamically based on input and output tokens consumed. Free models are priced at <strong>$0.02 / 1M in and $0.03 / 1M out</strong> for Free plan users, while all Paid plan users receive a <strong>10x priority discount at $0.002 / 1M in and $0.003 / 1M out</strong>.</li>
            <li>All paid plans allow accessing the full registry of models, though recommended selections exist per plan tier to optimize credit limits.</li>
            <li>Free and paid users can also use the <strong>Bring Your Own Key (BYOK)</strong> option to connect their own custom provider keys and URLs, bypassing UTIM quota limits entirely.</li>
            <li><strong>Credit Top-Up Payments & Conversion Rates</strong>: One-time credit top-ups (ranging from $2.00 to $4,500.00) are converted dynamically to Indian Rupees (INR) using real-time market exchange rates plus a platform markup fee. Top-up credits are added instantly to your account as bonus quota at <code>$1.00 USD = 1,000 credits</code>.</li>
          </ul>
        </div>
      </div>
    </section>
  );
}
