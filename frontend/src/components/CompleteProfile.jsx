/**
 * src/components/CompleteProfile.jsx
 * Burn-Ex — Complete Profile Onboarding Page
 *
 * 4-step profile completion form:
 *   Step 1 — Personal Info (avatar upload, name, DOB → auto age, gender)
 *   Step 2 — Body Metrics (height, weight)
 *   Step 3 — Contact Verification (mobile OTP + alternate mobile OTP)
 *   Step 4 — Fitness Goal
 *
 * All API calls use authenticatedFetch() from AuthService.
 */

import React, { useState, useRef, useCallback } from 'react';
import { authenticatedFetch } from '../auth/AuthService';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const GOAL_OPTIONS = [
  {
    value: 'Fat-loss',
    label: 'Fat Loss',
    description: 'Burn calories and shed body fat efficiently',
    emoji: '🔥',
    color: 'from-orange-400 to-red-500',
    bg: 'bg-orange-50 border-orange-200',
    activeBg: 'bg-orange-500',
  },
  {
    value: 'Muscle-gain',
    label: 'Muscle Gain',
    description: 'Build lean muscle mass and increase strength',
    emoji: '💪',
    color: 'from-blue-400 to-indigo-500',
    bg: 'bg-blue-50 border-blue-200',
    activeBg: 'bg-indigo-500',
  },
  {
    value: 'Endurance',
    label: 'Endurance',
    description: 'Improve cardiovascular fitness and stamina',
    emoji: '⚡',
    color: 'from-yellow-400 to-amber-500',
    bg: 'bg-yellow-50 border-yellow-200',
    activeBg: 'bg-amber-500',
  },
  {
    value: 'Hypertrophy',
    label: 'Hypertrophy',
    description: 'Maximise muscle size with progressive overload',
    emoji: '🏋️',
    color: 'from-purple-400 to-violet-500',
    bg: 'bg-purple-50 border-purple-200',
    activeBg: 'bg-violet-500',
  },
  {
    value: 'Weight-maintenance',
    label: 'Maintenance',
    description: 'Maintain current weight and stay fit',
    emoji: '⚖️',
    color: 'from-emerald-400 to-teal-500',
    bg: 'bg-emerald-50 border-emerald-200',
    activeBg: 'bg-emerald-500',
  },
];

function StepProgress({ current, total }) {
  return (
    <div className="flex items-center gap-2 mb-8">
      {Array.from({ length: total }).map((_, i) => (
        <React.Fragment key={i}>
          <div
            className={`flex items-center justify-center w-8 h-8 rounded-full text-xs font-extrabold transition-all duration-300 ${
              i < current
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                : i === current
                ? 'bg-indigo-100 text-indigo-600 ring-2 ring-indigo-500 ring-offset-2'
                : 'bg-slate-100 text-slate-400'
            }`}
          >
            {i < current ? '✓' : i + 1}
          </div>
          {i < total - 1 && (
            <div
              className={`flex-1 h-1 rounded-full transition-all duration-500 ${
                i < current ? 'bg-indigo-500' : 'bg-slate-100'
              }`}
            />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

function ErrorBanner({ message }) {
  if (!message) return null;
  return (
    <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-xs font-semibold flex items-start gap-2">
      <span className="text-red-500 mt-0.5 flex-shrink-0">⚠</span>
      <span>{message}</span>
    </div>
  );
}

function DevOTPBanner({ otp }) {
  if (!otp) return null;
  return (
    <div className="mb-4 px-4 py-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-800 text-xs font-semibold flex items-center gap-2">
      <span className="text-amber-500 flex-shrink-0">🧪</span>
      <span>Dev Mode OTP: <strong className="text-amber-900 tracking-widest text-sm">{otp}</strong></span>
    </div>
  );
}

// ── Utility ─────────────────────────────────────────────────────────────────
function calculateAge(dobString) {
  if (!dobString) return null;
  const dob = new Date(dobString);
  const today = new Date();
  let age = today.getFullYear() - dob.getFullYear();
  const m = today.getMonth() - dob.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < dob.getDate())) age--;
  return age >= 0 ? age : null;
}

// ── Main Component ───────────────────────────────────────────────────────────
export default function CompleteProfile({ authUser, onComplete }) {
  const [step, setStep] = useState(0); // 0..3
  const [globalError, setGlobalError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Step 1 — Personal Info
  const [avatarFile, setAvatarFile] = useState(null);
  const [avatarPreview, setAvatarPreview] = useState(authUser?.photoURL || '');
  const [name, setName] = useState(authUser?.name || '');
  const [dob, setDob] = useState('');
  const [gender, setGender] = useState('');
  const avatarInputRef = useRef(null);

  // Step 2 — Body Metrics
  const [heightCm, setHeightCm] = useState('');
  const [weightKg, setWeightKg] = useState('');

  // Step 3 — Contact OTP
  const [primaryPhone, setPrimaryPhone] = useState('');
  const [primaryOtpSent, setPrimaryOtpSent] = useState(false);
  const [primaryOtpCode, setPrimaryOtpCode] = useState('');
  const [primaryVerified, setPrimaryVerified] = useState(false);
  const [primaryDevOtp, setPrimaryDevOtp] = useState('');
  const [primaryOtpLoading, setPrimaryOtpLoading] = useState(false);

  const [altPhone, setAltPhone] = useState('');
  const [altOtpSent, setAltOtpSent] = useState(false);
  const [altOtpCode, setAltOtpCode] = useState('');
  const [altVerified, setAltVerified] = useState(false);
  const [altDevOtp, setAltDevOtp] = useState('');
  const [altOtpLoading, setAltOtpLoading] = useState(false);

  const [contactError, setContactError] = useState('');

  // Step 4 — Goal
  const [fitnessGoal, setFitnessGoal] = useState('Fat-loss');

  // ── Avatar upload ────────────────────────────────────────────────────────
  const handleAvatarChange = useCallback((e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setAvatarFile(file);
    setAvatarPreview(URL.createObjectURL(file));
  }, []);

  const uploadAvatar = useCallback(async () => {
    if (!avatarFile) return null;
    const form = new FormData();
    form.append('file', avatarFile);
    const res = await authenticatedFetch(`${API_BASE}/api/upload/avatar`, {
      method: 'POST',
      body: form,
      headers: {},  // Let browser set multipart boundary
    });
    if (!res.ok) throw new Error('Avatar upload failed');
    const data = await res.json();
    return data.url;
  }, [avatarFile]);

  // ── OTP helpers ──────────────────────────────────────────────────────────
  const sendOtp = useCallback(async (phone, field, setDevOtp, setSent, setLoading) => {
    setGlobalError('');
    setContactError('');
    if (!phone.trim()) { setContactError('Phone number is required.'); return; }
    setLoading(true);
    try {
      const res = await authenticatedFetch(`${API_BASE}/api/profile/send-otp`, {
        method: 'POST',
        body: JSON.stringify({ phone, field }),
      });
      const data = await res.json();
      if (!res.ok) { setContactError(data.detail || 'Failed to send OTP'); return; }
      setSent(true);
      if (data.dev_otp) setDevOtp(data.dev_otp);
    } catch (e) {
      setContactError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  const verifyOtp = useCallback(async (phone, code, field, setVerified, setLoading) => {
    setContactError('');
    if (!code.trim()) { setContactError('Please enter the OTP code.'); return; }
    setLoading(true);
    try {
      const res = await authenticatedFetch(`${API_BASE}/api/profile/verify-otp`, {
        method: 'POST',
        body: JSON.stringify({ phone, code, field }),
      });
      const data = await res.json();
      if (!res.ok) { setContactError(data.detail || 'Invalid OTP.'); return; }
      setVerified(true);
    } catch (e) {
      setContactError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  // ── Step Validation ──────────────────────────────────────────────────────
  const validateStep0 = () => {
    if (!name.trim()) { setGlobalError('Full name is required.'); return false; }
    if (!dob) { setGlobalError('Date of birth is required.'); return false; }
    const age = calculateAge(dob);
    if (age === null || age < 10 || age > 100) {
      setGlobalError('Please enter a valid date of birth (age 10–100).');
      return false;
    }
    if (!gender) { setGlobalError('Please select your gender.'); return false; }
    setGlobalError('');
    return true;
  };

  const validateStep1 = () => {
    const h = parseFloat(heightCm);
    const w = parseFloat(weightKg);
    if (!heightCm || isNaN(h) || h < 100 || h > 250) {
      setGlobalError('Height must be between 100 and 250 cm.');
      return false;
    }
    if (!weightKg || isNaN(w) || w < 20 || w > 300) {
      setGlobalError('Weight must be between 20 and 300 kg.');
      return false;
    }
    setGlobalError('');
    return true;
  };

  const validateStep2 = () => {
    if (!primaryVerified) {
      setGlobalError('Please verify your primary mobile number first.');
      return false;
    }
    if (!altVerified) {
      setGlobalError('Please verify your alternate mobile number first.');
      return false;
    }
    setGlobalError('');
    return true;
  };

  // ── Navigation ───────────────────────────────────────────────────────────
  const handleNext = () => {
    setGlobalError('');
    if (step === 0 && !validateStep0()) return;
    if (step === 1 && !validateStep1()) return;
    if (step === 2 && !validateStep2()) return;
    setStep((s) => s + 1);
  };

  // ── Final Submit ─────────────────────────────────────────────────────────
  const handleSubmit = useCallback(async () => {
    if (!fitnessGoal) { setGlobalError('Please select a fitness goal.'); return; }
    setSubmitting(true);
    setGlobalError('');
    try {
      // Upload avatar if changed
      if (avatarFile) {
        await uploadAvatar().catch((e) => console.warn('Avatar upload skipped:', e));
      }

      // Complete profile
      const res = await authenticatedFetch(`${API_BASE}/api/profile/complete`, {
        method: 'POST',
        body: JSON.stringify({
          name: name.trim(),
          date_of_birth: dob,
          gender,
          height_cm: parseFloat(heightCm),
          weight_kg: parseFloat(weightKg),
          mobile_number: primaryPhone.trim(),
          alternate_mobile_number: altPhone.trim(),
          fitness_goal: fitnessGoal,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setGlobalError(data.detail || 'Profile completion failed. Please try again.');
        return;
      }
      onComplete(data.profile);
    } catch (e) {
      setGlobalError('Network error. Please check your connection and try again.');
    } finally {
      setSubmitting(false);
    }
  }, [fitnessGoal, avatarFile, name, dob, gender, heightCm, weightKg, primaryPhone, altPhone, onComplete, uploadAvatar]);

  // ── Step labels ──────────────────────────────────────────────────────────
  const stepLabels = ['Personal Info', 'Body Metrics', 'Contact & OTP', 'Fitness Goal'];
  const age = dob ? calculateAge(dob) : null;

  return (
    <div
      style={{ minHeight: '100vh' }}
      className="bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900 flex items-center justify-center p-4"
    >
      {/* Background glow orbs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 -left-32 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 -right-32 w-96 h-96 bg-purple-600/15 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 w-full max-w-lg">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-indigo-600 mb-4 shadow-xl shadow-indigo-600/30">
            <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
              <path
                d="M16 2C16 2 10 9 10 15a6 6 0 0 0 6 6 6 6 0 0 0 6-6c0-3-2-6-2-6s-1 3-3 3c-1.5 0-2.5-1.5-2.5-3C14.5 7 16 2 16 2z"
                fill="white"
              />
            </svg>
          </div>
          <h1 className="text-3xl font-black text-white tracking-tight">Complete Your Profile</h1>
          <p className="text-slate-400 text-sm mt-1 font-medium">{stepLabels[step]}</p>
        </div>

        {/* Card */}
        <div className="bg-white/5 backdrop-blur-2xl border border-white/10 rounded-3xl p-8 shadow-2xl">
          <StepProgress current={step} total={4} />
          <ErrorBanner message={globalError} />

          {/* ─── STEP 0: Personal Info ─── */}
          {step === 0 && (
            <div className="space-y-5">
              {/* Avatar */}
              <div className="flex flex-col items-center gap-3 mb-2">
                <div
                  className="relative w-24 h-24 rounded-2xl overflow-hidden cursor-pointer border-2 border-dashed border-white/20 hover:border-indigo-400 transition group"
                  onClick={() => avatarInputRef.current?.click()}
                >
                  {avatarPreview ? (
                    <img src={avatarPreview} alt="Avatar" className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full bg-white/5 flex flex-col items-center justify-center text-white/50 text-[10px] font-bold uppercase tracking-wide">
                      <span className="text-2xl mb-1">📷</span>
                      Upload
                    </div>
                  )}
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition flex items-center justify-center text-white text-[10px] font-bold">
                    Change
                  </div>
                </div>
                <input
                  ref={avatarInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={handleAvatarChange}
                />
                <p className="text-white/40 text-[10px] font-medium">Click to upload profile picture</p>
              </div>

              {/* Name */}
              <div>
                <label className="block text-xs font-bold text-white/60 uppercase tracking-wider mb-1.5">
                  Full Name *
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your full name"
                  className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/20 transition text-sm font-medium"
                />
              </div>

              {/* DOB */}
              <div>
                <label className="block text-xs font-bold text-white/60 uppercase tracking-wider mb-1.5">
                  Date of Birth *
                </label>
                <input
                  type="date"
                  value={dob}
                  max={new Date().toISOString().split('T')[0]}
                  onChange={(e) => setDob(e.target.value)}
                  className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/20 transition text-sm font-medium"
                  style={{ colorScheme: 'dark' }}
                />
                {age !== null && (
                  <p className="text-indigo-300 text-xs font-semibold mt-1.5 ml-1">
                    Age: {age} years old
                  </p>
                )}
              </div>

              {/* Gender */}
              <div>
                <label className="block text-xs font-bold text-white/60 uppercase tracking-wider mb-2">
                  Gender *
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {['Male', 'Female', 'Other'].map((g) => (
                    <button
                      key={g}
                      type="button"
                      onClick={() => setGender(g.toLowerCase())}
                      className={`py-2.5 rounded-xl text-xs font-bold border transition-all ${
                        gender === g.toLowerCase()
                          ? 'bg-indigo-600 border-indigo-500 text-white shadow-md shadow-indigo-600/30'
                          : 'bg-white/5 border-white/10 text-white/60 hover:bg-white/10 hover:text-white'
                      }`}
                    >
                      {g}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ─── STEP 1: Body Metrics ─── */}
          {step === 1 && (
            <div className="space-y-5">
              <div>
                <label className="block text-xs font-bold text-white/60 uppercase tracking-wider mb-1.5">
                  Height (100 – 250 cm) *
                </label>
                <div className="relative">
                  <input
                    type="number"
                    value={heightCm}
                    min="100"
                    max="250"
                    onChange={(e) => setHeightCm(e.target.value)}
                    placeholder="e.g. 175"
                    className="w-full px-4 py-3 pr-14 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/20 transition text-sm font-medium"
                  />
                  <span className="absolute right-4 top-1/2 -translate-y-1/2 text-white/40 text-xs font-bold">cm</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-white/60 uppercase tracking-wider mb-1.5">
                  Weight (20 – 300 kg) *
                </label>
                <div className="relative">
                  <input
                    type="number"
                    value={weightKg}
                    min="20"
                    max="300"
                    step="0.1"
                    onChange={(e) => setWeightKg(e.target.value)}
                    placeholder="e.g. 70.5"
                    className="w-full px-4 py-3 pr-14 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/20 transition text-sm font-medium"
                  />
                  <span className="absolute right-4 top-1/2 -translate-y-1/2 text-white/40 text-xs font-bold">kg</span>
                </div>
              </div>

              {/* BMI preview */}
              {heightCm && weightKg && parseFloat(heightCm) > 0 && (
                <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                  <p className="text-white/40 text-[10px] uppercase font-bold tracking-wider mb-1">BMI Preview</p>
                  <p className="text-white font-black text-2xl">
                    {(parseFloat(weightKg) / Math.pow(parseFloat(heightCm) / 100, 2)).toFixed(1)}
                  </p>
                  <p className="text-white/40 text-xs mt-0.5">
                    {(() => {
                      const bmi = parseFloat(weightKg) / Math.pow(parseFloat(heightCm) / 100, 2);
                      if (bmi < 18.5) return 'Underweight';
                      if (bmi < 25) return 'Normal weight ✓';
                      if (bmi < 30) return 'Overweight';
                      return 'Obese';
                    })()}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* ─── STEP 2: Contact & OTP ─── */}
          {step === 2 && (
            <div className="space-y-6">
              {contactError && <ErrorBanner message={contactError} />}

              {/* Primary Mobile */}
              <div className="space-y-3">
                <label className="block text-xs font-bold text-white/60 uppercase tracking-wider">
                  Primary Mobile Number *
                </label>
                <div className="flex gap-2">
                  <input
                    type="tel"
                    value={primaryPhone}
                    onChange={(e) => { setPrimaryPhone(e.target.value); setPrimaryOtpSent(false); setPrimaryVerified(false); }}
                    placeholder="+91 9876543210"
                    disabled={primaryVerified}
                    className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/20 transition text-sm font-medium disabled:opacity-50"
                  />
                  {!primaryVerified && (
                    <button
                      type="button"
                      disabled={primaryOtpLoading || primaryOtpSent}
                      onClick={() => sendOtp(primaryPhone, 'mobile', setPrimaryDevOtp, setPrimaryOtpSent, setPrimaryOtpLoading)}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-bold rounded-xl transition whitespace-nowrap shadow-md shadow-indigo-600/20"
                    >
                      {primaryOtpLoading ? '...' : primaryOtpSent ? 'Resend' : 'Send OTP'}
                    </button>
                  )}
                  {primaryVerified && (
                    <div className="flex items-center gap-1.5 px-3 text-emerald-400 text-xs font-bold">
                      ✓ Verified
                    </div>
                  )}
                </div>
                <DevOTPBanner otp={primaryDevOtp} />
                {primaryOtpSent && !primaryVerified && (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={primaryOtpCode}
                      onChange={(e) => setPrimaryOtpCode(e.target.value)}
                      placeholder="Enter 6-digit OTP"
                      maxLength={6}
                      className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/20 transition text-sm font-medium tracking-widest"
                    />
                    <button
                      type="button"
                      disabled={primaryOtpLoading}
                      onClick={() => verifyOtp(primaryPhone, primaryOtpCode, 'mobile', setPrimaryVerified, setPrimaryOtpLoading)}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-bold rounded-xl transition shadow-md shadow-emerald-600/20"
                    >
                      {primaryOtpLoading ? '...' : 'Verify'}
                    </button>
                  </div>
                )}
              </div>

              {/* Alternate Mobile */}
              <div className="space-y-3">
                <label className="block text-xs font-bold text-white/60 uppercase tracking-wider">
                  Alternate Mobile Number *
                </label>
                <div className="flex gap-2">
                  <input
                    type="tel"
                    value={altPhone}
                    onChange={(e) => { setAltPhone(e.target.value); setAltOtpSent(false); setAltVerified(false); setContactError(''); }}
                    placeholder="+91 9876543211"
                    disabled={altVerified}
                    className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/20 transition text-sm font-medium disabled:opacity-50"
                  />
                  {!altVerified && (
                    <button
                      type="button"
                      disabled={altOtpLoading || altOtpSent}
                      onClick={() => {
                        if (altPhone.trim() === primaryPhone.trim()) {
                          setContactError('Alternative number cannot be the same as primary number.');
                          return;
                        }
                        sendOtp(altPhone, 'alternate_mobile', setAltDevOtp, setAltOtpSent, setAltOtpLoading);
                      }}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-bold rounded-xl transition whitespace-nowrap shadow-md shadow-indigo-600/20"
                    >
                      {altOtpLoading ? '...' : altOtpSent ? 'Resend' : 'Send OTP'}
                    </button>
                  )}
                  {altVerified && (
                    <div className="flex items-center gap-1.5 px-3 text-emerald-400 text-xs font-bold">
                      ✓ Verified
                    </div>
                  )}
                </div>
                <DevOTPBanner otp={altDevOtp} />
                {altOtpSent && !altVerified && (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={altOtpCode}
                      onChange={(e) => setAltOtpCode(e.target.value)}
                      placeholder="Enter 6-digit OTP"
                      maxLength={6}
                      className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/20 transition text-sm font-medium tracking-widest"
                    />
                    <button
                      type="button"
                      disabled={altOtpLoading}
                      onClick={() => verifyOtp(altPhone, altOtpCode, 'alternate_mobile', setAltVerified, setAltOtpLoading)}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-bold rounded-xl transition shadow-md shadow-emerald-600/20"
                    >
                      {altOtpLoading ? '...' : 'Verify'}
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ─── STEP 3: Fitness Goal ─── */}
          {step === 3 && (
            <div className="space-y-3">
              {GOAL_OPTIONS.map((g) => (
                <button
                  key={g.value}
                  type="button"
                  onClick={() => setFitnessGoal(g.value)}
                  className={`w-full flex items-center gap-4 p-4 rounded-2xl border text-left transition-all duration-200 ${
                    fitnessGoal === g.value
                      ? 'bg-indigo-600/20 border-indigo-500/60 shadow-md shadow-indigo-500/10'
                      : 'bg-white/5 border-white/10 hover:bg-white/10'
                  }`}
                >
                  <span className="text-2xl">{g.emoji}</span>
                  <div className="flex-1 min-w-0">
                    <strong className="text-white text-sm font-bold block">{g.label}</strong>
                    <p className="text-white/50 text-xs mt-0.5 leading-relaxed">{g.description}</p>
                  </div>
                  <div
                    className={`w-5 h-5 rounded-full border-2 flex-shrink-0 transition-all ${
                      fitnessGoal === g.value
                        ? 'border-indigo-400 bg-indigo-500'
                        : 'border-white/20 bg-transparent'
                    }`}
                  />
                </button>
              ))}
            </div>
          )}

          {/* ─── Navigation Buttons ─── */}
          <div className="flex gap-3 mt-8">
            {step > 0 && (
              <button
                type="button"
                onClick={() => { setGlobalError(''); setStep((s) => s - 1); }}
                className="px-6 py-3 border border-white/15 text-white/70 hover:text-white hover:bg-white/5 font-bold rounded-xl text-sm transition"
              >
                Back
              </button>
            )}
            {step < 3 ? (
              <button
                type="button"
                onClick={handleNext}
                className="flex-1 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-black rounded-xl text-sm shadow-lg shadow-indigo-600/20 transition active:scale-95"
              >
                Continue →
              </button>
            ) : (
              <button
                type="button"
                disabled={submitting}
                onClick={handleSubmit}
                className="flex-1 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 disabled:opacity-50 text-white font-black rounded-xl text-sm shadow-lg shadow-indigo-600/20 transition active:scale-95"
              >
                {submitting ? 'Saving Profile...' : '🚀 Complete Setup'}
              </button>
            )}
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-white/25 text-xs mt-6 font-medium">
          Burn-Ex &mdash; Your data is private and secure
        </p>
      </div>
    </div>
  );
}
