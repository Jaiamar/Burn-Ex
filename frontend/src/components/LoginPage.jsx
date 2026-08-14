import React, { useState, useCallback, useId } from 'react';
import {
  loginWithEmail,
  loginWithGoogle,
  sendPasswordReset,
  getFirebaseErrorMessage,
} from '../auth/AuthService';

// ─── SVG Icons ────────────────────────────────────────────────────────────

function FlameIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="flame-grad" x1="16" y1="2" x2="16" y2="30" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#FF6B35" />
          <stop offset="100%" stopColor="#EF4444" />
        </linearGradient>
      </defs>
      <path
        d="M16 2C16 2 10 9 10 15a6 6 0 0 0 6 6 6 6 0 0 0 6-6c0-3-2-6-2-6s-1 3-3 3c-1.5 0-2.5-1.5-2.5-3C14.5 7 16 2 16 2z"
        fill="url(#flame-grad)"
      />
      <path
        d="M16 20c0 0-3-2-3-5 0 0-1 2-1 4a4 4 0 0 0 4 4 4 4 0 0 0 4-4c0-1-0.5-2-0.5-2C19 19.5 17.5 20 16 20z"
        fill="#FF8C42"
        opacity="0.8"
      />
    </svg>
  );
}

function EyeIcon({ open }) {
  return open ? (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
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
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      style={{ animation: 'bx-spin 0.75s linear infinite' }}
    >
      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
    </svg>
  );
}

function GoogleLogo() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
    </svg>
  );
}

// ─── Pose-estimation SVG Overlay ──────────────────────────────────────────

function PoseOverlay() {
  // Keypoints mapped to the athlete image (as percentages of container)
  // Athlete is doing a push-up, left side view
  const nodes = [
    { id: 'nose',         x: 12,  y: 22, label: false },
    { id: 'l-shoulder',   x: 24,  y: 34, label: true },
    { id: 'r-shoulder',   x: 38,  y: 40, label: false },
    { id: 'l-elbow',      x: 18,  y: 51, label: true },
    { id: 'r-elbow',      x: 30,  y: 57, label: false },
    { id: 'l-wrist',      x: 14,  y: 65, label: true },
    { id: 'r-wrist',      x: 25,  y: 71, label: false },
    { id: 'l-hip',        x: 52,  y: 38, label: true },
    { id: 'r-hip',        x: 62,  y: 43, label: false },
    { id: 'l-knee',       x: 68,  y: 44, label: true },
    { id: 'r-knee',       x: 74,  y: 48, label: false },
    { id: 'l-ankle',      x: 80,  y: 55, label: false },
    { id: 'r-ankle',      x: 86,  y: 58, label: false },
  ];

  const connections = [
    ['nose', 'l-shoulder'],
    ['l-shoulder', 'r-shoulder'],
    ['l-shoulder', 'l-elbow'],
    ['l-elbow', 'l-wrist'],
    ['r-shoulder', 'r-elbow'],
    ['r-elbow', 'r-wrist'],
    ['l-shoulder', 'l-hip'],
    ['r-shoulder', 'r-hip'],
    ['l-hip', 'r-hip'],
    ['l-hip', 'l-knee'],
    ['r-hip', 'r-knee'],
    ['l-knee', 'l-ankle'],
    ['r-knee', 'r-ankle'],
  ];

  const nodeMap = Object.fromEntries(nodes.map((n) => [n.id, n]));

  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
    >
      <defs>
        <radialGradient id="node-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#6366F1" stopOpacity="0.6" />
          <stop offset="100%" stopColor="#6366F1" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Skeleton connections */}
      {connections.map(([a, b]) => {
        const na = nodeMap[a];
        const nb = nodeMap[b];
        if (!na || !nb) return null;
        return (
          <line
            key={`${a}-${b}`}
            x1={na.x} y1={na.y}
            x2={nb.x} y2={nb.y}
            stroke="#6366F1"
            strokeWidth="0.7"
            strokeOpacity="0.65"
          />
        );
      })}

      {/* Keypoint nodes */}
      {nodes.map((n) => (
        <g key={n.id}>
          {/* Glow halo */}
          <circle cx={n.x} cy={n.y} r="2.5" fill="url(#node-glow)" />
          {/* Outer ring */}
          <circle
            cx={n.x} cy={n.y} r="1.4"
            fill="white"
            stroke="#6366F1"
            strokeWidth="0.6"
            strokeOpacity="0.9"
          />
          {/* Center dot */}
          <circle cx={n.x} cy={n.y} r="0.55" fill="#6366F1" />
        </g>
      ))}
    </svg>
  );
}

// ─── Calorie HUD ──────────────────────────────────────────────────────────

function CalorieHUD() {
  return (
    <div style={{
      position: 'absolute',
      top: '12%',
      right: '4%',
      width: 90,
      height: 90,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexDirection: 'column',
    }}>
      {/* Circular progress ring */}
      <svg width="90" height="90" viewBox="0 0 90 90" style={{ position: 'absolute', top: 0, left: 0 }}>
        <circle
          cx="45" cy="45" r="40"
          fill="none"
          stroke="#E0E7FF"
          strokeWidth="5"
        />
        <circle
          cx="45" cy="45" r="40"
          fill="none"
          stroke="#6366F1"
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray="251.2"
          strokeDashoffset="62.8"
          transform="rotate(-90 45 45)"
          style={{ transition: 'stroke-dashoffset 1s ease' }}
        />
      </svg>
      <div style={{ position: 'relative', zIndex: 1, textAlign: 'center' }}>
        <div style={{ fontSize: 16, marginBottom: 1 }}>🔥</div>
        <div style={{
          fontSize: 18,
          fontWeight: 800,
          color: '#6366F1',
          lineHeight: 1,
          fontFamily: 'inherit',
        }}>238</div>
        <div style={{
          fontSize: 9,
          fontWeight: 700,
          color: '#94A3B8',
          letterSpacing: '0.08em',
          marginTop: 1,
        }}>KCAL</div>
      </div>
    </div>
  );
}

// ─── Feature Cards ────────────────────────────────────────────────────────

function FeatureCard({ icon, title, description }) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      flex: '1 1 0',
      minWidth: 0,
    }}>
      <div style={{
        width: 36,
        height: 36,
        borderRadius: 10,
        background: '#EEF2FF',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        {icon}
      </div>
      <div style={{ fontSize: 12, fontWeight: 700, color: '#111827', marginTop: 2 }}>{title}</div>
      <div style={{ fontSize: 11, color: '#64748B', lineHeight: 1.45 }}>{description}</div>
    </div>
  );
}

function ChartIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6366F1" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  );
}

function ZapIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6366F1" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6366F1" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

// ─── Input Field Component ────────────────────────────────────────────────

function InputField({
  id, label, type, placeholder, value, onChange,
  error, rightElement, onKeyDown,
}) {
  const [focused, setFocused] = useState(false);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label
        htmlFor={id}
        style={{ fontSize: 13, fontWeight: 600, color: '#111827' }}
      >
        {label}
      </label>
      <div style={{ position: 'relative' }}>
        <input
          id={id}
          type={type}
          placeholder={placeholder}
          value={value}
          onChange={onChange}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={onKeyDown}
          aria-invalid={!!error}
          aria-describedby={error ? `${id}-error` : undefined}
          style={{
            width: '100%',
            height: 46,
            padding: '0 44px 0 14px',
            background: '#FFFFFF',
            border: `1.5px solid ${error ? '#EF4444' : focused ? '#6366F1' : '#E2E8F0'}`,
            borderRadius: 10,
            fontSize: 14,
            color: '#111827',
            outline: 'none',
            boxShadow: focused
              ? error
                ? '0 0 0 3px rgba(239,68,68,0.12)'
                : '0 0 0 3px rgba(99,102,241,0.12)'
              : 'none',
            transition: 'border-color 0.18s ease, box-shadow 0.18s ease',
            boxSizing: 'border-box',
          }}
        />
        {rightElement && (
          <div style={{
            position: 'absolute',
            right: 14,
            top: '50%',
            transform: 'translateY(-50%)',
          }}>
            {rightElement}
          </div>
        )}
      </div>
      {error && (
        <p
          id={`${id}-error`}
          role="alert"
          style={{ fontSize: 12, color: '#EF4444', margin: 0 }}
        >
          {error}
        </p>
      )}
    </div>
  );
}

// ─── Validation Helpers ───────────────────────────────────────────────────

function validateEmail(email) {
  if (!email.trim()) return 'Email is required';
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
    return 'Please enter a valid email address';
  return '';
}

function validatePassword(password) {
  if (!password) return 'Password is required';
  if (password.length < 6) return 'Password must be at least 6 characters';
  return '';
}

// ─── Main Login Page Component ────────────────────────────────────────────

export default function LoginPage({ onLogin, onNavigateToSignup }) {
  // Form state
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd]   = useState(false);

  // Error state
  const [emailErr, setEmailErr]   = useState('');
  const [pwdErr, setPwdErr]       = useState('');
  const [authErr, setAuthErr]     = useState('');

  // Loading states
  const [isLoggingIn, setIsLoggingIn]       = useState(false);
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);

  // Forgot-password flow
  const [showForgot, setShowForgot]           = useState(false);
  const [forgotEmail, setForgotEmail]         = useState('');
  const [forgotMsg, setForgotMsg]             = useState('');
  const [forgotLoading, setForgotLoading]     = useState(false);

  // Window minimize/maximize state
  const [isMaximized, setIsMaximized] = useState(false);

  // IDs for accessibility
  const emailId = useId();
  const pwdId   = useId();

  // ── Handlers ────────────────────────────────────────────────────────────

  const handleEmailLogin = useCallback(async () => {
    const eErr = validateEmail(email);
    const pErr = validatePassword(password);
    setEmailErr(eErr);
    setPwdErr(pErr);
    if (eErr || pErr) return;

    console.log("[BX Auth] Attempting login with email:", email);
    setAuthErr('');
    setIsLoggingIn(true);
    try {
      const user = await loginWithEmail(email, password);
      console.log("[BX Auth] Login success. User:", user);
      onLogin(user);
    } catch (err) {
      console.error("[BX Auth] Login failed:", err);
      setAuthErr(getFriendlyError(err));
    } finally {
      setIsLoggingIn(false);
    }
  }, [email, password, onLogin]);

  const handleGoogleLogin = useCallback(async () => {
    console.log("[BX Auth] Attempting Google OAuth login");
    setAuthErr('');
    setIsGoogleLoading(true);
    try {
      const user = await loginWithGoogle();
      console.log("[BX Auth] Google OAuth login success. User:", user);
      onLogin(user);
    } catch (err) {
      console.error("[BX Auth] Google OAuth login failed:", err);
      setAuthErr(getFriendlyError(err));
    } finally {
      setIsGoogleLoading(false);
    }
  }, [onLogin]);

  const handleForgotSubmit = useCallback(async () => {
    const eErr = validateEmail(forgotEmail);
    if (eErr) { setForgotMsg(eErr); return; }
    setForgotLoading(true);
    try {
      await sendPasswordReset(forgotEmail);
      setForgotMsg('Password reset link sent! Check your inbox.');
    } catch {
      setForgotMsg('Failed to send reset email. Please try again.');
    } finally {
      setForgotLoading(false);
    }
  }, [forgotEmail]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter') handleEmailLogin();
  }, [handleEmailLogin]);

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

        @keyframes bx-spin {
          to { transform: rotate(360deg); }
        }
        @keyframes bx-fade-in {
          from { opacity: 0; transform: translateY(16px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes bx-slide-in {
          from { opacity: 0; transform: translateX(-12px); }
          to   { opacity: 1; transform: translateX(0); }
        }

        .bx-login-root * {
          box-sizing: border-box;
          font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
          -webkit-font-smoothing: antialiased;
        }

        .bx-login-btn-primary {
          background: linear-gradient(135deg, #4F46E5 0%, #6366F1 100%);
          color: white;
          border: none;
          border-radius: 10px;
          height: 48px;
          width: 100%;
          font-size: 15px;
          font-weight: 700;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          box-shadow: 0 4px 14px rgba(79, 70, 229, 0.35);
          transition: filter 0.18s ease, transform 0.12s ease, box-shadow 0.18s ease;
          outline: none;
        }
        .bx-login-btn-primary:hover:not(:disabled) {
          filter: brightness(1.08);
          box-shadow: 0 6px 20px rgba(79, 70, 229, 0.45);
          transform: translateY(-1px);
        }
        .bx-login-btn-primary:active:not(:disabled) {
          transform: scale(0.98) translateY(0);
          box-shadow: 0 2px 8px rgba(79, 70, 229, 0.3);
        }
        .bx-login-btn-primary:disabled {
          opacity: 0.7;
          cursor: not-allowed;
        }

        .bx-login-btn-google {
          background: white;
          color: #111827;
          border: 1.5px solid #E2E8F0;
          border-radius: 10px;
          height: 48px;
          width: 100%;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 10px;
          transition: background 0.15s ease, box-shadow 0.15s ease, transform 0.12s ease;
          outline: none;
        }
        .bx-login-btn-google:hover:not(:disabled) {
          background: #F9FAFB;
          box-shadow: 0 2px 8px rgba(0,0,0,0.08);
          transform: translateY(-1px);
        }
        .bx-login-btn-google:active:not(:disabled) {
          transform: scale(0.98);
        }
        .bx-login-btn-google:disabled {
          opacity: 0.7;
          cursor: not-allowed;
        }

        .bx-pwd-toggle {
          background: none;
          border: none;
          cursor: pointer;
          color: #94A3B8;
          padding: 4px;
          display: flex;
          align-items: center;
          transition: color 0.15s ease;
        }
        .bx-pwd-toggle:hover { color: #6366F1; }

        .bx-forgot-link {
          background: none;
          border: none;
          cursor: pointer;
          color: #6366F1;
          font-size: 12.5px;
          font-weight: 600;
          padding: 0;
          transition: color 0.15s ease;
          text-decoration: none;
        }
        .bx-forgot-link:hover { color: #4F46E5; text-decoration: underline; }

        .bx-signup-link {
          background: none;
          border: none;
          cursor: pointer;
          color: #6366F1;
          font-size: 13.5px;
          font-weight: 700;
          padding: 0;
          transition: color 0.15s ease;
        }
        .bx-signup-link:hover { color: #4F46E5; text-decoration: underline; }

        .bx-win-btn {
          width: 13px;
          height: 13px;
          border-radius: 50%;
          border: none;
          cursor: pointer;
          transition: filter 0.15s ease;
          flex-shrink: 0;
        }
        .bx-win-btn:hover { filter: brightness(0.85); }

        .bx-hero-section {
          animation: bx-slide-in 0.45s cubic-bezier(0.16,1,0.3,1) forwards;
        }
        .bx-login-section {
          animation: bx-fade-in 0.5s 0.1s cubic-bezier(0.16,1,0.3,1) both;
        }
      `}</style>

      {/* ── Page Background ── */}
      <div
        className="bx-login-root"
        style={{
          minHeight: '100vh',
          minWidth: '100vw',
          background: 'linear-gradient(135deg, #F0F4FF 0%, #F8FAFC 45%, #F4F0FF 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px 16px',
        }}
      >
        {/* ── Desktop Window ── */}
        <div
          role="main"
          style={{
            width: '100%',
            maxWidth: isMaximized ? '100%' : 1060,
            height: isMaximized ? '100vh' : undefined,
            minHeight: isMaximized ? '100vh' : undefined,
            background: 'white',
            borderRadius: isMaximized ? 0 : 20,
            border: '1px solid #E5E7EB',
            boxShadow: '0 24px 64px rgba(0,0,0,0.1), 0 8px 24px rgba(0,0,0,0.06)',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {/* ── Title Bar ── */}
          <div style={{
            height: 44,
            background: '#FAFAFA',
            borderBottom: '1px solid #F0F0F0',
            display: 'flex',
            alignItems: 'center',
            padding: '0 18px',
            gap: 8,
            flexShrink: 0,
            userSelect: 'none',
          }}>
            {/* Window control buttons */}
            <button
              className="bx-win-btn"
              aria-label="Close window"
              style={{ background: '#FF5F57' }}
            />
            <button
              className="bx-win-btn"
              aria-label="Minimize window"
              style={{ background: '#FFBD2E' }}
            />
            <button
              className="bx-win-btn"
              aria-label={isMaximized ? 'Restore window' : 'Maximize window'}
              style={{ background: '#28CA41' }}
              onClick={() => setIsMaximized((m) => !m)}
            />
            <div style={{
              flex: 1,
              textAlign: 'center',
              fontSize: 12,
              fontWeight: 500,
              color: '#9CA3AF',
              letterSpacing: '0.01em',
            }}>
              Burn-Ex — AI Fitness Platform
            </div>
          </div>

          {/* ── Two-Column Content ── */}
          <div style={{
            display: 'flex',
            flex: 1,
            overflow: 'hidden',
            flexDirection: 'row',
          }}>

            {/* ════════════════════════════════════════════════════════════
                LEFT HERO PANEL
            ════════════════════════════════════════════════════════════ */}
            <div
              className="bx-hero-section"
              style={{
                flex: '0 0 56%',
                background: 'linear-gradient(145deg, #F5F7FF 0%, #EEF0FA 60%, #F8F6FF 100%)',
                display: 'flex',
                flexDirection: 'column',
                padding: '36px 40px 32px',
                position: 'relative',
                overflow: 'hidden',
                minWidth: 0,
              }}
            >
              {/* Background decorative blobs */}
              <div style={{
                position: 'absolute', top: -60, left: -60,
                width: 240, height: 240,
                background: 'radial-gradient(circle, rgba(99,102,241,0.06) 0%, transparent 70%)',
                borderRadius: '50%',
                pointerEvents: 'none',
              }} />
              <div style={{
                position: 'absolute', bottom: 60, right: -40,
                width: 200, height: 200,
                background: 'radial-gradient(circle, rgba(99,102,241,0.08) 0%, transparent 70%)',
                borderRadius: '50%',
                pointerEvents: 'none',
              }} />

              {/* ── Logo ── */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, zIndex: 1 }}>
                <FlameIcon />
                <div>
                  <div style={{
                    fontSize: 20,
                    fontWeight: 800,
                    color: '#111827',
                    lineHeight: 1.1,
                    letterSpacing: '-0.3px',
                  }}>
                    Burn-Ex
                  </div>
                  <div style={{
                    fontSize: 11,
                    fontWeight: 500,
                    color: '#94A3B8',
                    marginTop: 1,
                  }}>
                    Move Better. Burn Smarter.
                  </div>
                </div>
              </div>

              {/* ── Headline ── */}
              <div style={{ marginTop: 28, zIndex: 1 }}>
                <h1 style={{
                  fontSize: 'clamp(26px, 3vw, 34px)',
                  fontWeight: 800,
                  lineHeight: 1.18,
                  color: '#111827',
                  margin: 0,
                }}>
                  <span style={{
                    background: 'linear-gradient(135deg, #4F46E5, #818CF8)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                  }}>
                    AI-Powered
                  </span>{' '}
                  Fitness<br />
                  That Understands You
                </h1>
                <p style={{
                  fontSize: 13.5,
                  color: '#64748B',
                  marginTop: 14,
                  lineHeight: 1.6,
                  maxWidth: 340,
                }}>
                  Real-time form analysis, personalized insights
                  and accurate calorie estimation — all on your device.
                </p>
              </div>

              {/* ── Athlete + Pose Overlay ── */}
              <div style={{
                flex: 1,
                position: 'relative',
                marginTop: 10,
                minHeight: 200,
                maxHeight: 280,
              }}>
                <CalorieHUD />
                <img
                  src="/athlete_pushup.png"
                  alt="Athlete performing a push-up with AI pose estimation overlay"
                  style={{
                    width: '88%',
                    height: '100%',
                    objectFit: 'contain',
                    objectPosition: 'bottom left',
                    display: 'block',
                  }}
                />
                {/* Pose overlay — absolute on top of image */}
                <div style={{
                  position: 'absolute',
                  bottom: 0,
                  left: 0,
                  width: '88%',
                  height: '100%',
                  pointerEvents: 'none',
                }}>
                  <PoseOverlay />
                </div>
              </div>

              {/* ── Feature Cards ── */}
              <div style={{
                display: 'flex',
                gap: 20,
                marginTop: 20,
                zIndex: 1,
              }}>
                <FeatureCard
                  icon={<ChartIcon />}
                  title="Smart Tracking"
                  description="AI tracks your reps, form & performance"
                />
                <FeatureCard
                  icon={<ZapIcon />}
                  title="Personalized"
                  description="Workouts and insights tailored for you"
                />
                <FeatureCard
                  icon={<ShieldIcon />}
                  title="Privacy First"
                  description="All processing happens on your device"
                />
              </div>
            </div>

            {/* Divider */}
            <div style={{
              width: 1,
              background: 'linear-gradient(to bottom, transparent, #E5E7EB 20%, #E5E7EB 80%, transparent)',
              flexShrink: 0,
            }} />

            {/* ════════════════════════════════════════════════════════════
                RIGHT LOGIN PANEL
            ════════════════════════════════════════════════════════════ */}
            <div
              className="bx-login-section"
              style={{
                flex: '0 0 44%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '40px 48px',
                minWidth: 0,
                background: 'white',
              }}
            >
              <div style={{ width: '100%', maxWidth: 360 }}>

                {/* ── Forgot password sub-view ── */}
                {showForgot ? (
                  <div style={{ animation: 'bx-fade-in 0.3s ease forwards' }}>
                    <h2 style={{ fontSize: 22, fontWeight: 800, color: '#111827', margin: '0 0 6px' }}>
                      Reset Password
                    </h2>
                    <p style={{ fontSize: 13.5, color: '#64748B', margin: '0 0 24px' }}>
                      Enter your email and we'll send a reset link.
                    </p>
                    <InputField
                      id="forgot-email"
                      label="Email"
                      type="email"
                      placeholder="Enter your email"
                      value={forgotEmail}
                      onChange={(e) => setForgotEmail(e.target.value)}
                      error=""
                      onKeyDown={(e) => e.key === 'Enter' && handleForgotSubmit()}
                    />
                    {forgotMsg && (
                      <p style={{
                        fontSize: 12.5,
                        color: forgotMsg.startsWith('Password reset') ? '#059669' : '#EF4444',
                        marginTop: 10,
                      }}>
                        {forgotMsg}
                      </p>
                    )}
                    <button
                      className="bx-login-btn-primary"
                      style={{ marginTop: 18 }}
                      onClick={handleForgotSubmit}
                      disabled={forgotLoading}
                    >
                      {forgotLoading ? <><SpinnerIcon /> Sending...</> : 'Send Reset Link'}
                    </button>
                    <div style={{ textAlign: 'center', marginTop: 16 }}>
                      <button
                        className="bx-forgot-link"
                        onClick={() => { setShowForgot(false); setForgotMsg(''); }}
                      >
                        ← Back to Login
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    {/* ── Heading ── */}
                    <div style={{ textAlign: 'center', marginBottom: 28 }}>
                      <h2 style={{
                        fontSize: 26,
                        fontWeight: 800,
                        color: '#111827',
                        margin: '0 0 6px',
                        letterSpacing: '-0.4px',
                      }}>
                        Welcome Back!
                      </h2>
                      <p style={{ fontSize: 13.5, color: '#64748B', margin: 0 }}>
                        Login to continue your fitness journey
                      </p>
                    </div>

                    {/* ── Auth error banner ── */}
                    {authErr && (
                      <div
                        role="alert"
                        style={{
                          background: '#FEF2F2',
                          border: '1px solid #FECACA',
                          borderRadius: 8,
                          padding: '10px 14px',
                          marginBottom: 16,
                          fontSize: 13,
                          color: '#DC2626',
                          fontWeight: 500,
                        }}
                      >
                        {authErr}
                      </div>
                    )}

                    {/* ── Email input ── */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                      <InputField
                        id={emailId}
                        label="Email"
                        type="email"
                        placeholder="Enter your email"
                        value={email}
                        onChange={(e) => { setEmail(e.target.value); setEmailErr(''); }}
                        error={emailErr}
                        onKeyDown={handleKeyDown}
                      />

                      {/* ── Password input ── */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        <label
                          htmlFor={pwdId}
                          style={{ fontSize: 13, fontWeight: 600, color: '#111827' }}
                        >
                          Password
                        </label>
                        <div style={{ position: 'relative' }}>
                          <input
                            id={pwdId}
                            type={showPwd ? 'text' : 'password'}
                            placeholder="Enter your password"
                            value={password}
                            onChange={(e) => { setPassword(e.target.value); setPwdErr(''); }}
                            onKeyDown={handleKeyDown}
                            aria-invalid={!!pwdErr}
                            aria-describedby={pwdErr ? `${pwdId}-error` : undefined}
                            style={{
                              width: '100%',
                              height: 46,
                              padding: '0 44px 0 14px',
                              background: '#FFFFFF',
                              border: `1.5px solid ${pwdErr ? '#EF4444' : '#E2E8F0'}`,
                              borderRadius: 10,
                              fontSize: 14,
                              color: '#111827',
                              outline: 'none',
                              boxSizing: 'border-box',
                              transition: 'border-color 0.18s ease, box-shadow 0.18s ease',
                            }}
                            onFocus={(e) => {
                              e.target.style.borderColor = pwdErr ? '#EF4444' : '#6366F1';
                              e.target.style.boxShadow = pwdErr
                                ? '0 0 0 3px rgba(239,68,68,0.12)'
                                : '0 0 0 3px rgba(99,102,241,0.12)';
                            }}
                            onBlur={(e) => {
                              e.target.style.borderColor = pwdErr ? '#EF4444' : '#E2E8F0';
                              e.target.style.boxShadow = 'none';
                            }}
                          />
                          <button
                            type="button"
                            className="bx-pwd-toggle"
                            aria-label={showPwd ? 'Hide password' : 'Show password'}
                            onClick={() => setShowPwd((v) => !v)}
                            style={{
                              position: 'absolute',
                              right: 12,
                              top: '50%',
                              transform: 'translateY(-50%)',
                            }}
                          >
                            <EyeIcon open={showPwd} />
                          </button>
                        </div>
                        {pwdErr && (
                          <p id={`${pwdId}-error`} role="alert" style={{ fontSize: 12, color: '#EF4444', margin: 0 }}>
                            {pwdErr}
                          </p>
                        )}
                      </div>

                      {/* ── Forgot password link ── */}
                      <div style={{ textAlign: 'right', marginTop: -6 }}>
                        <button
                          className="bx-forgot-link"
                          onClick={() => setShowForgot(true)}
                        >
                          Forgot Password?
                        </button>
                      </div>

                      {/* ── Login button ── */}
                      <button
                        className="bx-login-btn-primary"
                        onClick={handleEmailLogin}
                        disabled={isLoggingIn || isGoogleLoading}
                        aria-busy={isLoggingIn}
                      >
                        {isLoggingIn ? (
                          <><SpinnerIcon /> Signing in...</>
                        ) : (
                          'Login'
                        )}
                      </button>

                      {/* ── OR divider ── */}
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 12,
                        margin: '2px 0',
                      }}>
                        <div style={{ flex: 1, height: 1, background: '#E5E7EB' }} />
                        <span style={{ fontSize: 12, fontWeight: 600, color: '#9CA3AF', letterSpacing: '0.06em' }}>
                          OR
                        </span>
                        <div style={{ flex: 1, height: 1, background: '#E5E7EB' }} />
                      </div>

                      {/* ── Google Login button ── */}
                      <button
                        className="bx-login-btn-google"
                        onClick={handleGoogleLogin}
                        disabled={isLoggingIn || isGoogleLoading}
                        aria-busy={isGoogleLoading}
                      >
                        {isGoogleLoading ? (
                          <><SpinnerIcon /> Connecting...</>
                        ) : (
                          <><GoogleLogo /> Continue with Google</>
                        )}
                      </button>
                    </div>

                    {/* ── Sign up link ── */}
                    <div style={{
                      textAlign: 'center',
                      marginTop: 22,
                      fontSize: 13.5,
                      color: '#64748B',
                    }}>
                      Don't have an account?{' '}
                      <button
                        className="bx-signup-link"
                        onClick={onNavigateToSignup}
                      >
                        Sign up
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

// Error mapping is centralised in AuthService.getFirebaseErrorMessage
// Re-exported here for backward compatibility with the component
function getFriendlyError(err) {
  return getFirebaseErrorMessage(err);
}
