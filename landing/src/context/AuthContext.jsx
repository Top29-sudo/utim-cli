import React, { createContext, useContext, useState, useEffect } from 'react';
import {
    auth,
    onAuthStateChanged,
    signInWithEmail,
    signUpWithEmail,
    resendVerificationEmail,
    signInWithGoogle,
    signOut,
    getUserProfile,
    updateLastLogin,
    getIdToken
} from '../lib/firebase';
import { getApiUrl } from '../lib/api';

const AuthContext = createContext(null);

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [userProfile, setUserProfile] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Fallback timeout to ensure loading state doesn't get stuck
    useEffect(() => {
        const timeout = setTimeout(() => {
            console.log('[AuthContext] Timeout - setting loading to false');
            setLoading(false);
        }, 10000); // 10 second timeout

        return () => clearTimeout(timeout);
    }, []);

    useEffect(() => {
        const unsubscribe = onAuthStateChanged(async (firebaseUser) => {
            try {
                if (firebaseUser) {
                    setUser(firebaseUser);
                    // Fetch user profile from Firestore
                    try {
                        let profile = await getUserProfile(firebaseUser.uid);
                        
                        // If profile doesn't exist or we got permission error, create it
                        if (!profile) {
                            try {
                                const { createUserProfile } = await import('../lib/firebase');
                                await createUserProfile(firebaseUser, { 
                                    displayName: firebaseUser.displayName || '' 
                                });
                                profile = await getUserProfile(firebaseUser.uid);
                            } catch (createError) {
                                console.warn('[AuthContext] Could not create Firestore profile (likely permissions):', createError.message);
                            }
                        }
                        
                        // If we still don't have a profile (e.g. permission error), 
                        // fetch at least the plan from our own server
                        if (!profile) {
                            console.log('[AuthContext] Falling back to server for plan data...');
                            try {
                                const token = await firebaseUser.getIdToken();
                                const apiUrl = getApiUrl();
                                const planRes = await fetch(`${apiUrl}/api/user-plan`, {
                                    headers: { 'Authorization': `Bearer ${token}` }
                                });
                                const planData = await planRes.json();
                                profile = {
                                    uid: firebaseUser.uid,
                                    email: firebaseUser.email,
                                    plan: planData.plan || 'free',
                                    isFallback: true
                                };
                            } catch (serverErr) {
                                console.error('[AuthContext] Server plan fetch failed:', serverErr);
                            }
                        }
                        
                        setUserProfile(profile);
                        // Update last login time
                        try {
                            await updateLastLogin(firebaseUser.uid);
                        } catch (e) {
                            // Ignore login update failures
                        }
                    } catch (profileError) {
                        console.error('Error fetching user profile:', profileError);
                        // Check if it's a permission error - user might need to be created
                        if (profileError.code === 'permission-denied' || 
                            profileError.message?.includes('permission') ||
                            profileError.message?.includes('Permission')) {
                            
                            // Try server fallback directly
                            try {
                                const token = await firebaseUser.getIdToken();
                                const apiUrl = getApiUrl();
                                const planRes = await fetch(`${apiUrl}/api/user-plan`, {
                                    headers: { 'Authorization': `Bearer ${token}` }
                                });
                                const planData = await planRes.json();
                                setUserProfile({
                                    uid: firebaseUser.uid,
                                    email: firebaseUser.email,
                                    plan: planData.plan || 'free',
                                    isFallback: true
                                });
                            } catch (serverErr) {
                                console.error('[AuthContext] Server plan fetch fallback failed:', serverErr);
                            }
                        }
                    }
                } else {
                    setUser(null);
                    setUserProfile(null);
                }
            } catch (err) {
                console.error('Auth state change error:', err);
            } finally {
                // Always set loading to false - THIS IS CRITICAL
                console.log('[AuthContext] Setting loading to false');
                setLoading(false);
            }
        });

        return () => unsubscribe();
    }, []);

    const login = async (email, password) => {
        setError(null);
        try {
            const user = await signInWithEmail(email, password);
            return user;
        } catch (err) {
            setError(getErrorMessage(err.code));
            throw err;
        }
    };

    const register = async (email, password, displayName) => {
        setError(null);
        try {
            const user = await signUpWithEmail(email, password, displayName);
            return user;
        } catch (err) {
            if (err.code === 'auth/email-already-in-use') {
                console.log('[AuthContext] Email exists in Firebase Auth, signing in and setting displayName...');
                const signedInUser = await login(email, password);
                // Set displayName on the Firebase Auth profile since signUp was skipped
                if (signedInUser && displayName) {
                    try {
                        const { updateProfile, createUserProfile } = await import('../lib/firebase');
                        await updateProfile(signedInUser, { displayName });
                        // Also sync to Firestore profile
                        await createUserProfile(signedInUser, { displayName });
                        console.log('[AuthContext] DisplayName set after EMAIL_EXISTS fallback:', displayName);
                    } catch (profileErr) {
                        console.warn('[AuthContext] Failed to update profile displayName:', profileErr);
                    }
                }
                return signedInUser;
            }
            setError(getErrorMessage(err.code));
            throw err;
        }
    };

    const loginWithGoogle = async () => {
        setError(null);
        console.log('[AuthContext] Starting Google login...');
        try {
            const user = await signInWithGoogle();
            console.log('[AuthContext] Google login successful:', user.email);
            return user;
        } catch (err) {
            console.error('[AuthContext] Google login error:', err);
            console.error('[AuthContext] Error code:', err.code);
            setError(getErrorMessage(err.code));
            throw err;
        }
    };

    const logout = async () => {
        setError(null);
        try {
            await signOut();
        } catch (err) {
            setError(err.message);
            throw err;
        }
    };

    const getToken = async () => {
        return await getIdToken();
    };

    const refreshProfile = async () => {
        if (!user) return;
        console.log('[AuthContext] Refreshing user profile...');
        try {
            const token = await user.getIdToken();
            const apiUrl = getApiUrl();
            const planRes = await fetch(`${apiUrl}/api/user-plan`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const planData = await planRes.json();
            
            // Update the profile with the latest plan from the server
            const updatedProfile = {
                uid: user.uid,
                email: user.email,
                plan: planData.plan || 'free',
                isFallback: true
            };
            
            setUserProfile(updatedProfile);
            return updatedProfile;
        } catch (err) {
            console.error('[AuthContext] Error refreshing profile:', err);
        }
    };

    const sendOTP = async (email) => {
        const apiUrl = getApiUrl();
        const res = await fetch(`${apiUrl}/auth/code/request`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'Failed to send verification code.');
        }
        return data;
    };

    const verifyOTP = async (email, otpCode, password = null, displayName = null) => {
        const apiUrl = getApiUrl();
        const res = await fetch(`${apiUrl}/auth/code/verify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, otp_code: otpCode, password, display_name: displayName })
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'Invalid or expired verification code.');
        }
        return data;
    };

    const sendResetOTP = async (email) => {
        const apiUrl = getApiUrl();
        const res = await fetch(`${apiUrl}/auth/code/reset-request`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'Failed to send password reset code.');
        }
        return data;
    };

    const resetPasswordWithOTP = async (email, otpCode, newPassword) => {
        const apiUrl = getApiUrl();
        const res = await fetch(`${apiUrl}/auth/code/reset-confirm`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, otp_code: otpCode, new_password: newPassword })
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'Failed to reset password.');
        }
        return data;
    };

    const value = {
        user,
        userProfile,
        loading,
        error,
        login,
        register,
        sendOTP,
        verifyOTP,
        sendResetOTP,
        resetPasswordWithOTP,
        resendVerificationEmail,
        loginWithGoogle,
        logout,
        getToken,
        refreshProfile,
        isAuthenticated: !!user,
        // isEmailVerified is always true for authenticated users — our backend OTP system
        // is the real verification gate. Firebase's emailVerified flag is unreliable for
        // accounts provisioned via our OTP flow (REST API can't set it client-side).
        isEmailVerified: !!user
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
};

// Helper function to get user-friendly error messages
const getErrorMessage = (errorCode) => {
    switch (errorCode) {
        case 'auth/email-already-in-use':
            return 'This email is already registered. Please sign in instead.';
        case 'auth/invalid-email':
            return 'Invalid email address.';
        case 'auth/operation-not-allowed':
            return 'Email/password accounts are not enabled.';
        case 'auth/weak-password':
            return 'Password is too weak. Use at least 6 characters.';
        case 'auth/user-disabled':
            return 'This account has been disabled.';
        case 'auth/user-not-found':
            return 'No account found with this email.';
        case 'auth/wrong-password':
            return 'Incorrect password.';
        case 'auth/invalid-credential':
            return 'Invalid email or password.';
        case 'auth/too-many-requests':
            return 'Too many failed attempts. Please try again later.';
        case 'auth/popup-closed-by-user':
            return 'Sign-in popup was closed.';
        default:
            return 'An error occurred. Please try again.';
    }
};

export default AuthContext;
