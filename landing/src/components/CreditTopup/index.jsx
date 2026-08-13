import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { getApiUrl } from '../../lib/api';
import { DollarSign, Zap, Check, AlertCircle, RefreshCw, CreditCard } from 'lucide-react';
import '../ScrollytellingMain.css';

const API_URL = getApiUrl();

const detectIsIndian = () => {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (tz && (tz.includes('Kolkata') || tz.includes('Calcutta') || tz.includes('Asia/Kolkata'))) {
      return true;
    }
  } catch (e) {}
  
  try {
    const locale = navigator.language || navigator.userLanguage;
    if (locale && (locale.includes('-IN') || locale.toLowerCase() === 'in')) {
      return true;
    }
  } catch (e) {}
  
  return false;
};

export default function CreditTopup() {
  const { user, isAuthenticated } = useAuth();
  const [amount, setAmount] = useState('10');
  const [balance, setBalance] = useState(null);
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [isIndian, setIsIndian] = useState(detectIsIndian());


  useEffect(() => {
    if (isAuthenticated && user) {
      fetchBalance();
    }
  }, [isAuthenticated, user]);

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

  const fetchBalance = async () => {
    if (!user) return;
    try {
      setLoading(true);
      const token = await user.getIdToken(true);
      const response = await fetch(`${API_URL}/api/credits`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setBalance(data.balance);
      }
    } catch (err) {
      console.error('[CreditTopup] Error:', err);
    } finally {
      setLoading(false);
    }
  };

  const verifyPayment = async (chargeId, razorpayResponse) => {
    try {
      setProcessing(true);
      setError(null);

      const token = await user.getIdToken(true);
      const response = await fetch(`${API_URL}/api/credits/verify/${chargeId}`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json' 
        },
        body: JSON.stringify({
          razorpay_payment_id: razorpayResponse.razorpay_payment_id,
          razorpay_signature: razorpayResponse.razorpay_signature
        })
      });

      const data = await response.json();

      if (data.success && data.status === 'completed') {
        setError(null);
        setSuccessMsg(`✓ Top-up of $${parseFloat(amount).toFixed(2)} completed successfully!`);
        fetchBalance();
        setTimeout(() => setSuccessMsg(null), 5000);
      } else {
        setError(data.error || 'Payment verification failed');
      }
    } catch (err) {
      console.error('[CreditTopup] Verify error:', err);
      setError('Error verifying payment.');
    } finally {
      setProcessing(false);
    }
  };

  const handleTopup = async () => {
    const topupAmount = parseFloat(amount);

    if (isNaN(topupAmount) || topupAmount < 2) {
      setError('Minimum top-up amount is $2.00');
      return;
    }

    if (topupAmount > 4500) {
      setError('Maximum top-up amount is $4,500.00');
      return;
    }

    try {
      setProcessing(true);
      setError(null);

      const token = await user.getIdToken(true);
      const response = await fetch(`${API_URL}/api/credits/topup`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
          amount: topupAmount,
          currency: isIndian ? 'INR' : 'USD'
        })
      });

      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        setError('Server unavailable. Please try again later.');
        setProcessing(false);
        return;
      }

      const data = await response.json();

      if (data.success && data.orderId) {
        const options = {
          key: data.keyId,
          amount: data.amount,
          currency: data.currency,
          name: 'UTIM AI',
          description: `Top-up $${topupAmount.toFixed(2)} compute credits`,
          order_id: data.orderId,
          handler: function (resp) {
            verifyPayment(data.orderId, resp);
          },
          prefill: {
            email: user.email || ''
          },
          theme: {
            color: '#121214'
          },
          modal: {
            ondismiss: function() {
              setProcessing(false);
            }
          }
        };

        const rzp = new window.Razorpay(options);
        rzp.on('payment.failed', function (resp) {
          setProcessing(false);
          setError(resp.error.description || 'Payment failed');
        });
        rzp.open();
      } else {
        setError(data.error || 'Failed to create payment order');
        setProcessing(false);
      }
    } catch (err) {
      setError(err.message || 'An error occurred during payment initiation');
      setProcessing(false);
    }
  };

  const presetAmounts = [5, 10, 25, 50, 100];

  return (
    <div className="st-doc-card" style={{ marginTop: 24, border: '1px solid var(--border-cream)', background: '#FFFFFF', position: 'relative', zIndex: 1 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, borderBottom: '1px solid var(--border-cream)', paddingBottom: 16 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            <Zap size={15} /> Compute Credit Balance
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: 4 }}>
            {loading ? '...' : balance !== null ? `$${parseFloat(balance).toFixed(2)}` : '$0.00'}
          </div>
        </div>
        <button 
          onClick={fetchBalance}
          disabled={loading}
          style={{ background: 'transparent', border: '1px solid var(--border-cream)', borderRadius: 8, padding: '8px 12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 600, color: 'var(--text-body)' }}
        >
          <RefreshCw size={14} className={loading ? 'st-spin' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
        <div>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>
            Select Refill Amount (USD)
          </label>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {presetAmounts.map((preset) => {
              const isSelected = amount === String(preset);
              return (
                <button
                  key={preset}
                  type="button"
                  onClick={() => setAmount(String(preset))}
                  className={`st-term-prompt-chip ${isSelected ? 'active' : ''}`}
                  style={{ padding: '8px 16px', fontSize: 14, fontWeight: 700 }}
                >
                  ${preset}
                </button>
              );
            })}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', width: 140 }}>
            <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', fontWeight: 700, color: 'var(--text-muted)' }}>$</span>
            <input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              min="2"
              max="4500"
              step="1"
              style={{ width: '100%', padding: '10px 12px 10px 28px', border: '1px solid var(--border-cream)', borderRadius: 8, fontSize: 15, fontWeight: 700, background: 'var(--bg-cream-alt)', color: 'var(--text-primary)', outline: 'none' }}
            />
          </div>

          <button
            onClick={handleTopup}
            disabled={processing || !user}
            className="st-nav-primary-btn"
            style={{ padding: '10px 24px', display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 14, fontWeight: 700 }}
          >
            <CreditCard size={16} />
            <span>{processing ? 'Processing...' : `Pay $${parseFloat(amount || 0).toFixed(2)} via UPI / Card`}</span>
          </button>
        </div>

        {error && (
          <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', color: '#DC2626', padding: '10px 14px', borderRadius: 8, fontSize: 13.5, display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {successMsg && (
          <div style={{ background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.25)', color: '#059669', padding: '10px 14px', borderRadius: 8, fontSize: 13.5, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Check size={16} />
            <span>{successMsg}</span>
          </div>
        )}

        <div style={{ fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.6 }}>
          • Minimum refill: $2.00 • Maximum refill: $4,500.00 • Automatic INR conversion provided via UPI / Indian cards.
        </div>
      </div>
    </div>
  );
}
