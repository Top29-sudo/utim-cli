import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { 
  ArrowRight, Home, Zap, Shield, BookOpen, 
  ShoppingBag, History as HistoryIcon, HelpCircle, Gift, 
  User, LogOut, Menu, X, Terminal, ChevronRight 
} from 'lucide-react';

export default function ScrollytellingHeaderNav() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, userProfile, isAuthenticated, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  const navLinks = [
    { name: 'Home', path: '/', icon: Home },
    { name: 'Features', path: '/features', icon: Zap },
    { name: 'Pricing', path: '/pricing', icon: Shield },
    { name: 'Rewards', path: '/rewards', icon: Gift },
    { name: 'Documentation', path: '/docs', icon: BookOpen },
    { name: 'Marketplace', path: '/marketplace', icon: ShoppingBag },
    { name: 'Changelog', path: '/changelog', icon: HistoryIcon },
    { name: 'Referral', path: '/referral', icon: Gift },
    { name: 'Support', path: '/support', icon: HelpCircle },
  ];

  return (
    <>
      <header className={`st-navbar-wrapper ${scrolled ? 'st-navbar-scrolled' : ''}`}>
        <div className="st-navbar-inner">
          {/* Brand Logo & Title */}
          <Link to="/" className="st-nav-brand">
            <img src="/logo.png" alt="UTIM AI logo" className="st-brand-logo-img" />
            <div className="st-brand-text-group">
              <span className="st-brand-name">UTIM AI</span>
              <span className="st-brand-pill">CLI v2.1.3</span>
            </div>
          </Link>

          {/* Desktop Multi-Page Navigation Links */}
          <nav className="st-nav-links">
            {navLinks.map((link) => {
              const isActive = location.pathname === link.path;
              return (
                <Link
                  key={link.path}
                  to={link.path}
                  className={`st-nav-link ${isActive ? 'active' : ''}`}
                >
                  <span>{link.name}</span>
                  {isActive && <span className="st-nav-active-dot" />}
                </Link>
              );
            })}
          </nav>

          {/* Desktop User Action Buttons */}
          <div className="st-nav-actions">
            {isAuthenticated && user ? (
              <div className="st-nav-user-group">
                <Link to="/profile" className="st-nav-user-pill">
                  <div className="st-user-avatar-sm">
                    {user.photoURL ? (
                      <img src={user.photoURL} alt="Avatar" />
                    ) : (
                      <span>{user.displayName ? user.displayName.charAt(0).toUpperCase() : user.email.charAt(0).toUpperCase()}</span>
                    )}
                  </div>
                  <span className="st-user-name-text">Dashboard</span>
                </Link>
              </div>
            ) : (
              <>
                <Link to="/auth" className="st-nav-auth-btn">
                  Sign In
                </Link>
                <Link to="/auth?mode=signup" className="st-nav-primary-btn">
                  <span>Get Started</span>
                  <ArrowRight size={14} />
                </Link>
              </>
            )}

            {/* Mobile Hamburger Button */}
            <button
              type="button"
              className="st-mobile-toggle-btn"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
            </button>
          </div>
        </div>
      </header>

      {/* Mobile Drawer Navigation Overlay */}
      {mobileMenuOpen && (
        <div className="st-mobile-drawer-backdrop" onClick={() => setMobileMenuOpen(false)}>
          <div className="st-mobile-drawer-content" onClick={(e) => e.stopPropagation()}>
            <div className="st-mobile-drawer-header">
              <div className="st-nav-brand">
                <img src="/logo.png" alt="UTIM AI logo" className="st-brand-logo-img" />
                <span className="st-brand-name">UTIM AI</span>
              </div>
              <button 
                className="st-mobile-close-btn"
                onClick={() => setMobileMenuOpen(false)}
              >
                <X size={20} />
              </button>
            </div>

            <div className="st-mobile-drawer-links">
              {navLinks.map((link) => {
                const Icon = link.icon;
                const isActive = location.pathname === link.path;
                return (
                  <Link
                    key={link.path}
                    to={link.path}
                    className={`st-mobile-nav-link ${isActive ? 'active' : ''}`}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <Icon size={18} />
                      <span>{link.name}</span>
                    </div>
                    <ChevronRight size={16} color="var(--text-muted)" />
                  </Link>
                );
              })}
            </div>

            <div className="st-mobile-drawer-footer">
              {isAuthenticated && user ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <Link to="/profile" className="st-nav-primary-btn" style={{ width: '100%', justifyContent: 'center' }}>
                    <User size={16} />
                    <span>Open Dashboard ({user.email})</span>
                  </Link>
                  <button 
                    onClick={async () => { await logout(); navigate('/'); }}
                    className="st-btn-secondary"
                    style={{ width: '100%', padding: '10px', borderRadius: 8, fontSize: 13.5, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
                  >
                    <LogOut size={15} />
                    <span>Sign Out</span>
                  </button>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <Link to="/auth?mode=signup" className="st-nav-primary-btn" style={{ width: '100%', justifyContent: 'center' }}>
                    <span>Get Started Free</span>
                    <ArrowRight size={14} />
                  </Link>
                  <Link to="/auth" className="st-btn-secondary" style={{ width: '100%', padding: '10px', borderRadius: 8, textAlign: 'center' }}>
                    Sign In
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
