/**
 * src/components/WorkoutCountdown.jsx
 * Burn-Ex — Fullscreen Workout Start Countdown & Position Detection Overlay
 * 
 * Features:
 *   - Dark transparent glassmorphism backdrop
 *   - Large animated countdown number with SVG progress ring
 *   - Live camera body detection & confidence indicator
 *   - Voice & audio cue controls (Mute / Unmute)
 *   - Accessible high-contrast typography & keyboard shortcuts (Escape, Space)
 */

import React, { useEffect } from 'react';
import { Volume2, VolumeX, X, Camera, AlertTriangle, Sparkles, CheckCircle2 } from 'lucide-react';

export function WorkoutCountdown({
  status, // 'DETECTING_BODY' | 'COUNTDOWN'
  secondsLeft,
  totalSeconds = 5,
  exerciseName = 'Workout',
  bodyDetected = false,
  bodyConfidence = 0,
  isMuted = false,
  onToggleMute,
  onCancel
}) {
  // Keyboard shortcut listener (Escape to cancel, Space to toggle mute)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        if (onCancel) onCancel();
      } else if (e.key === ' ' || e.code === 'Space') {
        e.preventDefault();
        if (onToggleMute) onToggleMute();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onCancel, onToggleMute]);

  if (status !== 'DETECTING_BODY' && status !== 'COUNTDOWN') {
    return null;
  }

  // SVG Circle Dimensions
  const size = 280;
  const strokeWidth = 14;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progressRatio = totalSeconds > 0 ? Math.max(0, Math.min(1, secondsLeft / totalSeconds)) : 0;
  const strokeDashoffset = circumference * (1 - progressRatio);

  const isDetecting = status === 'DETECTING_BODY';

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/90 backdrop-blur-2xl flex flex-col justify-between p-6 md:p-12 font-sans select-none overflow-hidden animate-in fade-in duration-300">
      
      {/* ─── TOP HEADER BAR ─── */}
      <div className="flex items-center justify-between w-full max-w-5xl mx-auto">
        
        {/* Exercise Badge */}
        <div className="flex items-center gap-3 bg-white/10 border border-white/15 px-4 py-2 rounded-2xl backdrop-blur-md">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-ping" />
          <span className="text-white text-xs font-black uppercase tracking-wider">
            {exerciseName} Live Studio
          </span>
        </div>

        {/* Position Detection Indicator Pill */}
        <div className={`flex items-center gap-2.5 px-4 py-2 rounded-2xl text-xs font-bold transition-all backdrop-blur-md ${
          bodyDetected 
            ? 'bg-emerald-500/20 border border-emerald-500/40 text-emerald-300' 
            : 'bg-amber-500/20 border border-amber-500/40 text-amber-300 animate-pulse'
        }`}>
          <Camera size={16} className={bodyDetected ? 'text-emerald-400' : 'text-amber-400'} />
          <span>
            {bodyDetected 
              ? `Full Body Visible (${Math.round(bodyConfidence)}%)` 
              : `Detecting Position (${Math.round(bodyConfidence)}%)`}
          </span>
        </div>

        {/* Controls: Mute Audio & Cancel */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onToggleMute}
            className="p-3 bg-white/10 hover:bg-white/20 border border-white/15 rounded-2xl text-white transition active:scale-95 shadow-lg"
            title={isMuted ? "Unmute Voice Guidance (Space)" : "Mute Voice Guidance (Space)"}
          >
            {isMuted ? <VolumeX size={20} className="text-red-400" /> : <Volume2 size={20} className="text-emerald-400" />}
          </button>

          <button
            type="button"
            onClick={onCancel}
            className="p-3 bg-white/10 hover:bg-red-500/20 border border-white/15 hover:border-red-500/40 rounded-2xl text-white hover:text-red-300 transition active:scale-95 shadow-lg"
            title="Cancel Countdown (Esc)"
          >
            <X size={20} />
          </button>
        </div>
      </div>

      {/* ─── CENTRAL TIMER OVERLAY ─── */}
      <div className="flex-1 flex flex-col items-center justify-center text-center my-8">
        
        {/* Detection Warning Banner if body is not visible */}
        {isDetecting ? (
          <div className="max-w-md bg-amber-500/10 border border-amber-500/30 rounded-3xl p-6 mb-8 text-center backdrop-blur-lg scale-in">
            <div className="w-14 h-14 bg-amber-500/20 rounded-2xl flex items-center justify-center mx-auto mb-3 text-amber-400">
              <AlertTriangle size={28} />
            </div>
            <h2 className="text-lg font-black text-amber-200">Full Body Not Detected</h2>
            <p className="text-amber-300/80 text-xs font-medium mt-1 leading-relaxed">
              Please step back 4–5 meters so your full body is visible in the camera frame.
            </p>
          </div>
        ) : (
          <div className="mb-4">
            <span className="text-indigo-400 font-extrabold text-xs uppercase tracking-widest block mb-1">
              GET READY
            </span>
            <h1 className="text-2xl md:text-3xl font-black text-white tracking-tight">
              Workout starts in
            </h1>
          </div>
        )}

        {/* Circular Progress Ring + Large Timer Number */}
        <div className="relative flex items-center justify-center my-4">
          
          <svg width={size} height={size} className="transform -rotate-90">
            <defs>
              <linearGradient id="countdownGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#818CF8" />
                <stop offset="100%" stopColor="#C084FC" />
              </linearGradient>
            </defs>

            {/* Background Track */}
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              stroke="rgba(255, 255, 255, 0.1)"
              strokeWidth={strokeWidth}
              fill="transparent"
            />

            {/* Progress Stroke */}
            {!isDetecting && (
              <circle
                cx={size / 2}
                cy={size / 2}
                r={radius}
                stroke="url(#countdownGradient)"
                strokeWidth={strokeWidth}
                fill="transparent"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                style={{ transition: 'stroke-dashoffset 1s linear' }}
              />
            )}
          </svg>

          {/* Center Number / Status */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            {isDetecting ? (
              <div className="flex flex-col items-center gap-2">
                <Camera size={44} className="text-amber-400 animate-pulse" />
                <span className="text-xs font-extrabold text-amber-300 uppercase tracking-wider">
                  Positioning...
                </span>
              </div>
            ) : secondsLeft > 0 ? (
              <div key={secondsLeft} className="flex flex-col items-center animate-in zoom-in-75 duration-300">
                <span className="text-7xl md:text-8xl font-black text-white tracking-tighter drop-shadow-lg">
                  {secondsLeft}
                </span>
              </div>
            ) : (
              <div className="flex flex-col items-center animate-bounce">
                <span className="text-5xl font-black text-emerald-400 tracking-tight">
                  GO!
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Guidance Instruction */}
        <p className="text-white/60 text-xs md:text-sm font-medium mt-6 max-w-sm leading-relaxed">
          {isDetecting 
            ? "Waiting for body detection in camera view..." 
            : "Stand in camera frame. Tracking will begin automatically."}
        </p>

      </div>

      {/* ─── FOOTER TIP BAR ─── */}
      <div className="w-full max-w-xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 bg-white/5 border border-white/10 px-5 py-2.5 rounded-2xl backdrop-blur-md">
          <Sparkles size={14} className="text-indigo-400 flex-shrink-0" />
          <span className="text-white/70 text-xs font-semibold">
            Tip: Keep laptop or phone at waist level for maximum AI joint accuracy.
          </span>
        </div>
      </div>

    </div>
  );
}

export default WorkoutCountdown;
