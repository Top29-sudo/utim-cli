import React, { useState } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { useScroll } from 'framer-motion'
import PowershellUI from './components/PowershellUI'
import AuthPage from './pages/AuthPage'
import ProfilePage from './pages/ProfilePage'
import AuthCallback from './pages/AuthCallback'
import IntroScene from './components/IntroScene'
import ActivatePage from './pages/ActivatePage'
import PricingPage from './pages/PricingPage'
import SEOHead from './components/SEOHead'
import VsClaudeCode from './pages/VsClaudeCode'
import VsAntigravity from './pages/VsAntigravity'

function App() {
  const location = useLocation()
  const { scrollYProgress } = useScroll()
  const [introPlayed, setIntroPlayed] = useState(location.pathname !== '/')

  const handleIntroComplete = () => {
    setIntroPlayed(true);
  };

  if (!introPlayed) {
    return <IntroScene onComplete={handleIntroComplete} />;
  }

  return (
    <div className="App">
      {/* Per-page SEO meta tags – updates <head> on every route change */}
      <SEOHead path={location.pathname} />

      <Routes>
        <Route path="/" element={<PowershellUI />} />
        <Route path="/features" element={<PowershellUI />} />
        <Route path="/about" element={<PowershellUI />} />
        <Route path="/pricing" element={<PowershellUI />} />
        <Route path="/support" element={<PowershellUI />} />
        <Route path="/contacts" element={<PowershellUI />} />
        <Route path="/connect" element={<PowershellUI />} />
        <Route path="/docs" element={<PowershellUI />} />
        <Route path="/terms" element={<PowershellUI />} />
        <Route path="/privacy" element={<PowershellUI />} />
        <Route path="/license" element={<PowershellUI />} />
        <Route path="/refund" element={<PowershellUI />} />
        <Route path="/changelog" element={<PowershellUI />} />
        <Route path="/referral" element={<PowershellUI />} />
        <Route path="/referrals" element={<PowershellUI />} />
        <Route path="/marketplace" element={<PowershellUI />} />

        {/* Comparison landing pages – crawlable static content for Google */}
        <Route path="/vs-claude-code" element={<VsClaudeCode />} />
        <Route path="/vs-antigravity" element={<VsAntigravity />} />

        {/* Auth & account */}
        <Route path="/auth" element={<AuthPage />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/activate" element={<ActivatePage />} />
        <Route path="/pricing-checkout" element={<PricingPage />} />

        {/* Catch-all */}
        <Route path="*" element={<PowershellUI />} />
      </Routes>
    </div>
  )
}

export default App
