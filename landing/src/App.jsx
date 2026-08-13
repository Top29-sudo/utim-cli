import React from 'react';
import { Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import FeaturesPage from './pages/FeaturesPage';
import DocsPage from './pages/DocsPage';
import AboutPage from './pages/AboutPage';
import SupportPage from './pages/SupportPage';
import ChangelogPage from './pages/ChangelogPage';
import LegalPage from './pages/LegalPage';
import MarketplacePage from './pages/MarketplacePage';
import CleanPricingPage from './pages/PricingPage/CleanPricingPage';
import PricingPage from './pages/PricingPage';
import VsClaudeCode from './pages/VsClaudeCode';
import VsAntigravity from './pages/VsAntigravity';
import VsCursor from './pages/VsCursor';
import VsAider from './pages/VsAider';
import AuthPage from './pages/AuthPage';
import AuthCallback from './pages/AuthCallback';
import ProfilePage from './pages/ProfilePage';
import ActivatePage from './pages/ActivatePage';
import ReferralPage from './pages/ReferralPage';
import RewardsPage from './pages/RewardsPage';
import ScrollToTop from './components/ScrollToTop';

function App() {
  return (
    <div className="App">
      <ScrollToTop />
      <Routes>
        {/* Core Product Pages */}
        <Route path="/" element={<HomePage />} />
        <Route path="/features" element={<FeaturesPage />} />
        <Route path="/pricing" element={<PricingPage />} />
        <Route path="/pricing-checkout" element={<PricingPage />} />
        <Route path="/rewards" element={<RewardsPage />} />
        <Route path="/docs" element={<DocsPage />} />
        <Route path="/marketplace" element={<MarketplacePage />} />
        <Route path="/changelog" element={<ChangelogPage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/support" element={<SupportPage />} />

        {/* Legal & Policies Pages */}
        <Route path="/terms" element={<LegalPage type="terms" />} />
        <Route path="/privacy" element={<LegalPage type="privacy" />} />
        <Route path="/refund" element={<LegalPage type="refund" />} />
        <Route path="/license" element={<LegalPage type="license" />} />

        {/* Dedicated Competitor Comparison Pages */}
        <Route path="/vs-claude-code" element={<VsClaudeCode />} />
        <Route path="/vs-antigravity" element={<VsAntigravity />} />
        <Route path="/vs-cursor" element={<VsCursor />} />
        <Route path="/vs-aider" element={<VsAider />} />

        {/* App & User Account Pages */}
        <Route path="/auth" element={<AuthPage />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/activate" element={<ActivatePage />} />
        <Route path="/referral" element={<ReferralPage />} />
        <Route path="/referrals" element={<ReferralPage />} />

        {/* Fallback */}
        <Route path="*" element={<HomePage />} />
      </Routes>
    </div>
  );
}

export default App;
