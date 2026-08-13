import React from 'react';
import ScrollytellingHeaderNav from '../../components/ScrollytellingHeaderNav';
import ScrollytellingPricing from '../../components/ScrollytellingPricing';
import ScrollytellingFooter from '../../components/ScrollytellingFooter';
import SEOHead from '../../components/SEOHead';
import { Sparkles, CreditCard, Shield, Zap } from 'lucide-react';
import '../../components/ScrollytellingMain.css';

export default function CleanPricingPage() {
  return (
    <div className="st-page-root">
      <SEOHead
        title="Pricing & Compute Node Subscriptions — UTIM AI CLI"
        description="Flexible compute node subscriptions for UTIM CLI: Free ($0/mo), Hobby ($7/mo), Pro ($25/mo), Max ($55/mo), and Ultimate ($110/mo). BYOK supported."
        canonical="https://utim.dev/pricing"
      />
      <ScrollytellingHeaderNav />

      {/* Page Hero Header */}
      <div style={{ padding: '60px 24px 20px 24px', textAlign: 'center' }}>
        <div className="st-container">
          <h1 className="st-section-title" style={{ fontSize: 'clamp(2.4rem, 4.5vw, 3.6rem)' }}>
            Simple, Predictable Compute Pricing
          </h1>
          <p className="st-section-subtitle" style={{ maxWidth: 740, margin: '0 auto' }}>
            Choose the plan that fits your engineering speed. Upgrade, downgrade, or cancel anytime. All paid plans include rollover Quota Bank and priority compute.
          </p>
        </div>
      </div>

      {/* 5-Tier Pricing Grid & Plan Notes */}
      <ScrollytellingPricing />

      <ScrollytellingFooter />
    </div>
  );
}
