import React, { useState, useCallback, useId } from 'react';
import { registerWithEmail, loginWithGoogle, getFirebaseErrorMessage } from '../auth/AuthService';

function FlameIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
      <defs>
        <linearGradient id="flame-grad-s" x1="16" y1="2" x2="16" y2="30" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#FF6B35" />
          <stop offset="100%" stopColor="#EF4444" />
        </linearGradient>
      </defs>
      <path d="M16 2C16 2 10 9 10 15a6 6 0 0 0 6 6 6 6 0 0 0 6-6c0-3-2-6-2-6s-1 3-3 3c-1.5 0-2.5-1.5-2.5-3C14.5 7 16 2 16 2z" fill="url(#flame-grad-s)" />
      <path d="M16 20c0 0-3-2-3-5 0 0-1 2-1 4a4 4 0 0 0 4 4 4 4 0 0 0 4-4c0-1-0.5-2-0.5-2C19 19.5 17.5 20 16 20z" fill="#FF8C42" opacity="0.8" />
    </svg>
  );
}

function EyeIcon({ open }) {
  return open ? (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
    </svg>
  ) : (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
      style={{ animation: 'bx-spin 0.75s linear infinite' }}>
      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
    </svg>
  );
}

function GoogleLogo() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
    </svg>
  );
}

function validate(name, email, password, confirm) {
  const errors = {};
  if (!name.trim()) errors.name = 'Full name is required';
  if (!email.trim()) errors.email = 'Email is required';
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errors.email = 'Please enter a valid email';
  if (!password) errors.password = 'Password is required';
  else if (password.length < 6) errors.password = 'Password must be at least 6 characters';
  if (password !== confirm) errors.confirm = 'Passwords do not match';
  return errors;
}

export default function SignupPage({ onLogin, onNavigateToLogin }) {
  const [name, setName]         = useState('');
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm]   = useState('');
  const [showPwd, setShowPwd]   = useState(false);
  const [showCfm, setShowCfm]   = useState(false);
  const [errors, setErrors]     = useState({});
  const [authErr, setAuthErr]   = useState('');
  const [loading, setLoading]   = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  const nameId  = useId();
  const emailId = useId();
  const pwdId   = useId();
  const cfmId   = useId();

  const handleSignup = useCallback(async () => {
    const errs = validate(name, email, password, confirm);
    setErrors(errs);
    if (Object.keys(errs).length) return;
    console.log("[BX Auth] Attempting signup with email:", email);
    setAuthErr('');
    setLoading(true);
    try {
      const user = await registerWithEmail(email, password, name);
      console.log("[BX Auth] Signup success. User:", user);
      onLogin(user);
    } catch (err) {
      console.error("[BX Auth] Signup failed:", err);
      setAuthErr(getFriendlyError(err));
    } finally {
      setLoading(false);
    }
  }, [name, email, password, confirm, onLogin]);

  const handleGoogle = useCallback(async () => {
    console.log("[BX Auth] Attempting Google OAuth signup");
    setAuthErr('');
    setGoogleLoading(true);
    try {
      const user = await loginWithGoogle();
      console.log("[BX Auth] Google OAuth signup success. User:", user);
      onLogin(user);
    } catch (err) {
      console.error("[BX Auth] Google OAuth signup failed:", err);
      setAuthErr(getFriendlyError(err));
    } finally {
      setGoogleLoading(false);
    }
  }, [onLogin]);

  const handleKeyDown = (e) => { if (e.key === 'Enter') handleSignup(); };

  const inputStyle = (field) => ({
    width: '100%',
    height: 44,
    padding: '0 44px 0 14px',
    background: '#FFFFFF',
    border: `1.5px solid ${errors[field] ? '#EF4444' : '#E2E8F0'}`,
    borderRadius: 10,
    fontSize: 14,
    color: '#111827',
    outline: 'none',
    boxSizing: 'border-box',
    transition: 'border-color 0.18s ease, box-shadow 0.18s ease',
  });

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        @keyframes bx-spin { to { transform: rotate(360deg); } }
        @keyframes bx-fade-su { from { opacity:0; transform: translateY(12px); } to { opacity:1; transform: translateY(0); } }
        .bx-su-root * { box-sizing: border-box; font-family: 'Inter', ui-sans-serif, sans-serif; -webkit-font-smoothing: antialiased; }
        .bx-su-primary { background: linear-gradient(135deg, #4F46E5 0%, #6366F1 100%); color: white; border: none; border-radius: 10px; height: 46px; width: 100%; font-size: 14px; font-weight: 700; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px; box-shadow: 0 4px 14px rgba(79,70,229,0.3); transition: filter 0.15s, transform 0.12s; outline: none; }
        .bx-su-primary:hover:not(:disabled) { filter: brightness(1.08); transform: translateY(-1px); }
        .bx-su-primary:active:not(:disabled) { transform: scale(0.98); }
        .bx-su-primary:disabled { opacity: 0.7; cursor: not-allowed; }
        .bx-su-google { background: white; color: #111827; border: 1.5px solid #E2E8F0; border-radius: 10px; height: 46px; width: 100%; font-size: 14px; font-weight: 600; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 10px; transition: background 0.15s, box-shadow 0.15s, transform 0.12s; outline: none; }
        .bx-su-google:hover:not(:disabled) { background: #F9FAFB; box-shadow: 0 2px 8px rgba(0,0,0,0.08); transform: translateY(-1px); }
        .bx-su-google:disabled { opacity: 0.7; cursor: not-allowed; }
        .bx-su-eye { background: none; border: none; cursor: pointer; color: #94A3B8; padding: 4px; display: flex; align-items: center; transition: color 0.15s; }
        .bx-su-eye:hover { color: #6366F1; }
        .bx-su-link { background: none; border: none; cursor: pointer; color: #6366F1; font-size: 13.5px; font-weight: 700; padding: 0; transition: color 0.15s; }
        .bx-su-link:hover { color: #4F46E5; text-decoration: underline; }
        .bx-win-btn-su { width: 13px; height: 13px; border-radius: 50%; border: none; cursor: pointer; transition: filter 0.15s; flex-shrink: 0; }
        .bx-win-btn-su:hover { filter: brightness(0.85); }
      `}</style>

      <div className="bx-su-root" style={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #F0F4FF 0%, #F8FAFC 45%, #F4F0FF 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px 16px',
      }}>
        <div style={{
          width: '100%',
          maxWidth: 500,
          background: 'white',
          borderRadius: 20,
          border: '1px solid #E5E7EB',
          boxShadow: '0 24px 64px rgba(0,0,0,0.1)',
          overflow: 'hidden',
          animation: 'bx-fade-su 0.4s ease forwards',
        }}>
          {/* Title bar */}
          <div style={{
            height: 44,
            background: '#FAFAFA',
            borderBottom: '1px solid #F0F0F0',
            display: 'flex',
            alignItems: 'center',
            padding: '0 18px',
            gap: 8,
            userSelect: 'none',
          }}>
            <button className="bx-win-btn-su" aria-label="Close" style={{ background: '#FF5F57' }} />
            <button className="bx-win-btn-su" aria-label="Minimize" style={{ background: '#FFBD2E' }} />
            <button className="bx-win-btn-su" aria-label="Maximize" style={{ background: '#28CA41' }} />
            <div style={{ flex: 1, textAlign: 'center', fontSize: 12, fontWeight: 500, color: '#9CA3AF' }}>
              Burn-Ex — Create Account
            </div>
          </div>

          <div style={{ padding: '36px 48px 40px' }}>
            {/* Logo */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 24 }}>
              <FlameIcon />
              <div>
                <div style={{ fontSize: 17, fontWeight: 800, color: '#111827', lineHeight: 1.1 }}>Burn-Ex</div>
                <div style={{ fontSize: 10, color: '#94A3B8', fontWeight: 500 }}>Move Better. Burn Smarter.</div>
              </div>
            </div>

            {/* Heading */}
            <h1 style={{ fontSize: 22, fontWeight: 800, color: '#111827', margin: '0 0 6px' }}>
              Create your account
            </h1>
            <p style={{ fontSize: 13, color: '#64748B', margin: '0 0 24px' }}>
              Start your AI-powered fitness journey today.
            </p>

            {authErr && (
              <div role="alert" style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: '10px 14px', marginBottom: 16, fontSize: 13, color: '#DC2626', fontWeight: 500 }}>
                {authErr}
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {/* Name */}
              <div>
                <label htmlFor={nameId} style={{ fontSize: 13, fontWeight: 600, color: '#111827', display: 'block', marginBottom: 6 }}>Full Name</label>
                <input id={nameId} type="text" placeholder="Enter your full name" value={name}
                  onChange={(e) => { setName(e.target.value); setErrors(p => ({ ...p, name: '' })); }}
                  onKeyDown={handleKeyDown} style={{ ...inputStyle('name'), paddingRight: 14 }}
                  onFocus={(e) => { e.target.style.borderColor = errors.name ? '#EF4444' : '#6366F1'; e.target.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.12)'; }}
                  onBlur={(e) => { e.target.style.borderColor = errors.name ? '#EF4444' : '#E2E8F0'; e.target.style.boxShadow = 'none'; }}
                />
                {errors.name && <p role="alert" style={{ fontSize: 12, color: '#EF4444', margin: '4px 0 0' }}>{errors.name}</p>}
              </div>

              {/* Email */}
              <div>
                <label htmlFor={emailId} style={{ fontSize: 13, fontWeight: 600, color: '#111827', display: 'block', marginBottom: 6 }}>Email</label>
                <input id={emailId} type="email" placeholder="Enter your email" value={email}
                  onChange={(e) => { setEmail(e.target.value); setErrors(p => ({ ...p, email: '' })); }}
                  onKeyDown={handleKeyDown} style={{ ...inputStyle('email'), paddingRight: 14 }}
                  onFocus={(e) => { e.target.style.borderColor = errors.email ? '#EF4444' : '#6366F1'; e.target.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.12)'; }}
                  onBlur={(e) => { e.target.style.borderColor = errors.email ? '#EF4444' : '#E2E8F0'; e.target.style.boxShadow = 'none'; }}
                />
                {errors.email && <p role="alert" style={{ fontSize: 12, color: '#EF4444', margin: '4px 0 0' }}>{errors.email}</p>}
              </div>

              {/* Password */}
              <div>
                <label htmlFor={pwdId} style={{ fontSize: 13, fontWeight: 600, color: '#111827', display: 'block', marginBottom: 6 }}>Password</label>
                <div style={{ position: 'relative' }}>
                  <input id={pwdId} type={showPwd ? 'text' : 'password'} placeholder="Create a password (min 6 chars)" value={password}
                    onChange={(e) => { setPassword(e.target.value); setErrors(p => ({ ...p, password: '' })); }}
                    onKeyDown={handleKeyDown} style={inputStyle('password')}
                    onFocus={(e) => { e.target.style.borderColor = errors.password ? '#EF4444' : '#6366F1'; e.target.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.12)'; }}
                    onBlur={(e) => { e.target.style.borderColor = errors.password ? '#EF4444' : '#E2E8F0'; e.target.style.boxShadow = 'none'; }}
                  />
                  <button type="button" className="bx-su-eye" aria-label={showPwd ? 'Hide' : 'Show'}
                    onClick={() => setShowPwd(v => !v)}
                    style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)' }}>
                    <EyeIcon open={showPwd} />
                  </button>
                </div>
                {errors.password && <p role="alert" style={{ fontSize: 12, color: '#EF4444', margin: '4px 0 0' }}>{errors.password}</p>}
              </div>

              {/* Confirm */}
              <div>
                <label htmlFor={cfmId} style={{ fontSize: 13, fontWeight: 600, color: '#111827', display: 'block', marginBottom: 6 }}>Confirm Password</label>
                <div style={{ position: 'relative' }}>
                  <input id={cfmId} type={showCfm ? 'text' : 'password'} placeholder="Repeat your password" value={confirm}
                    onChange={(e) => { setConfirm(e.target.value); setErrors(p => ({ ...p, confirm: '' })); }}
                    onKeyDown={handleKeyDown} style={inputStyle('confirm')}
                    onFocus={(e) => { e.target.style.borderColor = errors.confirm ? '#EF4444' : '#6366F1'; e.target.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.12)'; }}
                    onBlur={(e) => { e.target.style.borderColor = errors.confirm ? '#EF4444' : '#E2E8F0'; e.target.style.boxShadow = 'none'; }}
                  />
                  <button type="button" className="bx-su-eye" aria-label={showCfm ? 'Hide' : 'Show'}
                    onClick={() => setShowCfm(v => !v)}
                    style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)' }}>
                    <EyeIcon open={showCfm} />
                  </button>
                </div>
                {errors.confirm && <p role="alert" style={{ fontSize: 12, color: '#EF4444', margin: '4px 0 0' }}>{errors.confirm}</p>}
              </div>

              <button className="bx-su-primary" onClick={handleSignup} disabled={loading || googleLoading} style={{ marginTop: 4 }}>
                {loading ? <><SpinnerIcon /> Creating account...</> : 'Create Account'}
              </button>

              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ flex: 1, height: 1, background: '#E5E7EB' }} />
                <span style={{ fontSize: 12, fontWeight: 600, color: '#9CA3AF', letterSpacing: '0.06em' }}>OR</span>
                <div style={{ flex: 1, height: 1, background: '#E5E7EB' }} />
              </div>

              <button className="bx-su-google" onClick={handleGoogle} disabled={loading || googleLoading}>
                {googleLoading ? <><SpinnerIcon /> Connecting...</> : <><GoogleLogo /> Continue with Google</>}
              </button>
            </div>

            <div style={{ textAlign: 'center', marginTop: 20, fontSize: 13.5, color: '#64748B' }}>
              Already have an account?{' '}
              <button className="bx-su-link" onClick={onNavigateToLogin}>Sign in</button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function getFriendlyError(err) {
  return getFirebaseErrorMessage(err);
}
