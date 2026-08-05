import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './PromoModal.css';

const PromoModal = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const [timeLeft, setTimeLeft] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const targetDate = new Date('2026-08-01T00:00:00'); // End of July 31, 2026
    const timer = setInterval(() => {
      const now = new Date();
      const diff = targetDate - now;
      if (diff <= 0) {
        setTimeLeft('Promotion Ended');
        clearInterval(timer);
      } else {
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
        const minutes = Math.floor((diff / (1000 * 60)) % 60);
        const seconds = Math.floor((diff / 1000) % 60);
        setTimeLeft(`${days}d ${hours}h ${minutes}m ${seconds}s`);
      }
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const handleCopy = () => {
    navigator.clipboard.writeText("npm install -g @emend-ai/utim");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!isOpen) return null;

  return (
    <div className="promo-modal-backdrop" onClick={onClose}>
      <div className="promo-modal-box" onClick={(e) => e.stopPropagation()}>
        {/* Terminal Header */}
        <div className="promo-modal-header">
          <div className="promo-header-title">
            <span className="promo-prompt">$</span> utim promo --july-special
          </div>
          <button className="promo-modal-close-btn" onClick={onClose} title="Close window">[×]</button>
        </div>

        <div className="promo-modal-body">
          {/* Badge & Timer */}
          <div className="promo-badge-row">
            <div className="promo-badge">✦ JULY SPECIAL: 50% OFF IMAGE GEN & 20% OFF BLENDER 3D</div>
            <div className="promo-timer-pill">
              Ends in: <strong>{timeLeft || 'Calculating...'}</strong>
            </div>
          </div>

          {/* Description */}
          <div className="promo-details">
            <h3 className="promo-title">July Special Price Drop</h3>
            <p className="promo-desc">
              Enjoy discounted compute rates across AI Image Generation and Blender 3D Model Generation for a limited time.
            </p>

            {/* Discounts List */}
            <div className="promo-offers-list">
              <div className="promo-offer-card">
                <div className="offer-tag green">50% OFF</div>
                <div className="offer-info">
                  <div className="offer-name">AI Image Generation</div>
                  <div className="offer-sub">FLUX.1 Schnell & OpenRouter text-to-image synthesis</div>
                </div>
              </div>

              <div className="promo-offer-card">
                <div className="offer-tag amber">20% OFF</div>
                <div className="offer-info">
                  <div className="offer-name">Blender 3D Model Generation</div>
                  <div className="offer-sub">Tripo v3.1, P1, Auto-Rigging & Animation Retargeting</div>
                </div>
              </div>
            </div>
          </div>

          {/* CLI Command Box */}
          <div className="promo-cli-section">
            <div className="promo-cli-label">&gt;_ INSTALL UTIM CLI TO START GENERATING</div>
            <div className="promo-cli-box" onClick={handleCopy} title="Click to copy install command">
              <code>npm install -g @emend-ai/utim</code>
              <button className="promo-copy-btn">
                {copied ? '✓ Copied!' : 'Copy'}
              </button>
            </div>
            <div className="promo-cli-hint">
              Run <code className="promo-code-inline">utim</code> in your local terminal to build 3D assets, execute agentic tasks & launch local tools.
            </div>
          </div>

          {/* Action Buttons */}
          <div className="promo-actions">
            <button className="promo-btn-primary" onClick={handleCopy}>
              {copied ? '✓ COPIED TO CLIPBOARD' : '[+] COPY CLI INSTALL COMMAND'}
            </button>
            <button className="promo-btn-secondary" onClick={() => { onClose(); navigate('/pricing'); }}>
              [$] VIEW PRICING & TIERS
            </button>
            <button className="promo-btn-dim" onClick={onClose}>
              [×] CLOSE
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PromoModal;
