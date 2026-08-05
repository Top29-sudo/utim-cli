import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import './CreditTopup.css';
import { getApiUrl } from '../../lib/api';

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

const CreditTopup = () => {
    const { user, isAuthenticated } = useAuth();
    const [amount, setAmount] = useState('10');
    const [balance, setBalance] = useState(null);
    const [loading, setLoading] = useState(false);
    const [processing, setProcessing] = useState(false);
    const [error, setError] = useState(null);
    const [isIndian, setIsIndian] = useState(detectIsIndian());

    // Dynamically detect user country via GeoIP with timezone fallback
    useEffect(() => {
        fetch('https://ipapi.co/json/')
            .then(res => res.json())
            .then(data => {
                if (data && data.country_code) {
                    setIsIndian(data.country_code === 'IN');
                }
            })
            .catch(() => {});
    }, []);

    // Fetch current balance
    useEffect(() => {
        if (isAuthenticated && user) {
            fetchBalance();
        }
    }, [isAuthenticated, user]);

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
                // Payment confirmed — refresh balance
                setError(null);
                fetchBalance();
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
                return;
            }

            const data = await response.json();

            if (data.success && data.orderId) {
                // Initialize Razorpay
                const options = {
                    key: data.keyId,
                    amount: data.amount,
                    currency: data.currency,
                    name: 'U.T.I.M AI',
                    description: `Top-up $${topupAmount.toFixed(2)} credits`,
                    order_id: data.orderId,
                    handler: function (response) {
                        // Payment successful, verify signature
                        verifyPayment(data.orderId, response);
                    },
                    prefill: {
                        email: user.email || ''
                    },
                    theme: {
                        color: '#3b82f6'
                    },
                    modal: {
                        ondismiss: function() {
                            setProcessing(false);
                        }
                    }
                };

                const rzp = new window.Razorpay(options);
                rzp.on('payment.failed', function (response) {
                    setProcessing(false);
                    setError(response.error.description || 'Payment failed');
                });
                rzp.open();
            } else {
                setError(data.error || 'Failed to create payment order');
                setProcessing(false);
            }
        } catch (err) {
            setError(err.message || 'An error occurred');
            setProcessing(false);
        }
    };

    const presetAmounts = [5, 10, 20, 50];

    return (
        <div className="term-md-card" style={{ marginTop: '24px', fontFamily: 'monospace' }}>
            <div className="term-md-card-border-top" style={{ color: '#222' }}>
                ┌── <span style={{ color: '#fff', fontWeight: 'bold' }}>COMPUTE CREDIT REFILL</span> ──────────────────────────────────────────────
            </div>
            <div className="term-md-card-content" style={{ padding: '16px 20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px dashed rgba(255,255,255,0.06)', paddingBottom: '12px' }}>
                    <span style={{ color: '#fff', fontSize: '0.85rem', fontWeight: 'bold' }}>CURRENT BALANCE:</span>
                    <span style={{ color: '#00F0FF', fontSize: '1.25rem', fontWeight: 'bold' }}>
                        {loading ? '...' : balance !== null ? `$${parseFloat(balance).toFixed(2)}` : '$0.00'}
                    </span>
                </div>

                <div className="topup-form" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
                        <span style={{ color: '#fff', fontSize: '0.8rem', fontWeight: 'bold' }}>TOP-UP AMOUNT (USD):</span>
                        <div className="preset-amounts" style={{ display: 'flex', gap: '16px', userSelect: 'none' }}>
                            {presetAmounts.map((preset) => {
                                const isSelected = amount === String(preset);
                                return (
                                    <span
                                        key={preset}
                                        style={{
                                            fontSize: '0.9rem',
                                            cursor: 'pointer',
                                            color: isSelected ? '#00F0FF' : '#aaa',
                                            fontWeight: isSelected ? 'bold' : 'normal',
                                            transition: 'color 0.15s'
                                        }}
                                        onClick={() => setAmount(String(preset))}
                                    >
                                        {isSelected ? `[ $${preset} ]` : `  $${preset}  `}
                                    </span>
                                );
                            })}
                        </div>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', marginTop: '4px' }}>
                        <div className="amount-input-wrapper" style={{ display: 'flex', alignItems: 'center', background: 'rgba(0, 0, 0, 0.3)', border: '1px dashed rgba(0, 240, 255, 0.2)', borderRadius: '4px', overflow: 'hidden', width: '180px' }}>
                            <span className="amount-prefix" style={{ padding: '8px 12px', color: '#fff', fontSize: '0.9rem', fontWeight: 'bold', borderRight: '1px dashed rgba(0, 240, 255, 0.2)' }}>$</span>
                            <input
                                type="number"
                                className="amount-input"
                                style={{ flex: 1, padding: '8px 12px', background: 'transparent', border: 'none', color: '#fff', fontSize: '0.95rem', fontWeight: 'bold', outline: 'none', fontFamily: 'monospace' }}
                                value={amount}
                                onChange={(e) => setAmount(e.target.value)}
                                min="2"
                                step="1"
                                placeholder="10"
                            />
                        </div>

                        <button
                            className="term-btn-action"
                            style={{
                                padding: '10px 24px',
                                cursor: processing || !user ? 'not-allowed' : 'pointer',
                                background: 'transparent',
                                color: processing || !user ? '#666' : '#00F0FF',
                                border: '1px solid',
                                borderColor: processing || !user ? 'rgba(255,255,255,0.05)' : 'rgba(0, 240, 255, 0.3)',
                                fontFamily: 'monospace',
                                fontWeight: 'bold',
                                fontSize: '0.85rem',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                transition: 'all 0.2s',
                                borderRadius: '4px'
                            }}
                            onMouseEnter={(e) => {
                                if (!processing && user) {
                                    e.currentTarget.style.background = 'rgba(0, 240, 255, 0.04)';
                                    e.currentTarget.style.borderColor = 'rgba(0, 240, 255, 0.5)';
                                    e.currentTarget.style.color = '#fff';
                                }
                            }}
                            onMouseLeave={(e) => {
                                if (!processing && user) {
                                    e.currentTarget.style.background = 'transparent';
                                    e.currentTarget.style.borderColor = 'rgba(0, 240, 255, 0.3)';
                                    e.currentTarget.style.color = '#00F0FF';
                                }
                            }}
                            onClick={handleTopup}
                            disabled={processing || !user}
                        >
                            {processing ? (
                                <>
                                    <span className="spinner"></span>
                                    &gt; INITIALIZING.TRANSACTION() ...
                                </>
                            ) : (
                                <>
                                    &gt; EXECUTE.PAYMENT(UPI_CARD)
                                </>
                            )}
                        </button>
                    </div>

                    {error && <p className="topup-error" style={{ color: '#e74856', fontSize: '0.8rem', background: 'rgba(231, 72, 86, 0.05)', border: '1px solid rgba(231, 72, 86, 0.15)', padding: '8px 12px', borderRadius: '4px', margin: '8px 0 0 0' }}>{error}</p>}

                    <p className="topup-info" style={{ color: '#aaa', fontSize: '0.72rem', marginTop: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        * Min top-up: $2.00 • Max top-up: $4,500.00 • Platform markup fees vary from 2% to 5%
                    </p>
                </div>
            </div>
            <div className="term-md-card-border-bottom" style={{ color: '#222' }}>
                └───────────────────────────────────────────────────────────────────────
            </div>
        </div>
    );
};

export default CreditTopup;
