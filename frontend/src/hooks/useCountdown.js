/**
 * src/hooks/useCountdown.js
 * Burn-Ex — Custom React Hook for Workout Countdown & Audio/Voice Orchestration
 * 
 * Manages position detection validation, countdown intervals, Web Audio API synth tones,
 * and voice guidance calls during workout start & resume sequences.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import voiceService from '../services/voiceService';

export function useCountdown({ initialSeconds = 10, onComplete } = {}) {
  const [status, setStatus] = useState('IDLE'); // 'IDLE' | 'DETECTING_BODY' | 'COUNTDOWN' | 'ACTIVE' | 'PAUSED'
  const [secondsLeft, setSecondsLeft] = useState(initialSeconds);
  const [bodyConfidence, setBodyConfidence] = useState(0);
  const [bodyDetected, setBodyDetected] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [exerciseName, setExerciseName] = useState('Workout');

  const timerRef = useRef(null);
  const audioCtxRef = useRef(null);
  const totalSecondsRef = useRef(initialSeconds);
  const statusRef = useRef(status);
  const bodyDetectedRef = useRef(bodyDetected);
  const onCompleteRef = useRef(onComplete);

  statusRef.current = status;
  bodyDetectedRef.current = bodyDetected;
  onCompleteRef.current = onComplete;

  // Initialize Web Audio Context on user interaction
  const getAudioContext = useCallback(() => {
    if (typeof window === 'undefined') return null;
    if (!audioCtxRef.current) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        audioCtxRef.current = new AudioCtx();
      }
    }
    if (audioCtxRef.current && audioCtxRef.current.state === 'suspended') {
      audioCtxRef.current.resume().catch(() => {});
    }
    return audioCtxRef.current;
  }, []);

  // Web Audio API tick beep sound (800Hz sine wave for 80ms)
  const playTickSound = useCallback(() => {
    if (isMuted) return;
    try {
      const ctx = getAudioContext();
      if (!ctx) return;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = 800; // 800 Hz beep
      gain.gain.setValueAtTime(0.15, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.08);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.08);
    } catch (e) {
      console.warn('[BX Audio] Tick sound failed:', e);
    }
  }, [getAudioContext, isMuted]);

  // Web Audio API completion chime sound (C-Major triad sweep)
  const playGoChime = useCallback(() => {
    if (isMuted) return;
    try {
      const ctx = getAudioContext();
      if (!ctx) return;
      const notes = [523.25, 659.25, 783.99, 1046.50]; // C5, E5, G5, C6
      notes.forEach((freq, idx) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'triangle';
        osc.frequency.value = freq;
        const startTime = ctx.currentTime + idx * 0.08;
        gain.gain.setValueAtTime(0.2, startTime);
        gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.35);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(startTime);
        osc.stop(startTime + 0.35);
      });
    } catch (e) {
      console.warn('[BX Audio] Go chime failed:', e);
    }
  }, [getAudioContext, isMuted]);

  // Clear running countdown intervals and speech queues
  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const toggleMute = useCallback(() => {
    setIsMuted(prev => {
      const next = !prev;
      voiceService.setMuted(next);
      return next;
    });
  }, []);

  // Update body detection confidence (0 - 100%)
  const updateBodyConfidence = useCallback((conf) => {
    const confidence = Math.min(100, Math.max(0, parseFloat(conf) || 0));
    setBodyConfidence(confidence);
    const isDetected = confidence >= 70;
    setBodyDetected(isDetected);

    // If waiting for body detection and user steps into frame, start countdown!
    if (statusRef.current === 'DETECTING_BODY' && isDetected) {
      console.log('[BX Countdown] Full body detected (conf = ' + confidence + '%). Starting countdown sequence.');
      setStatus('COUNTDOWN');
      voiceService.announce('Get ready. Workout starts in ' + totalSecondsRef.current + ' seconds.');
    }
  }, []);

  // Trigger mobile vibration if supported
  const triggerVibration = useCallback((pattern = [100]) => {
    if (typeof window !== 'undefined' && 'navigator' in window && navigator.vibrate) {
      try {
        navigator.vibrate(pattern);
      } catch (e) {}
    }
  }, []);

  // Start initial workout start countdown (e.g. 5s)
  const startStartCountdown = useCallback((name = 'Workout', seconds = 5, initialConfidence = 0) => {
    clearTimer();
    voiceService.stop();
    setExerciseName(name);
    totalSecondsRef.current = seconds;
    setSecondsLeft(seconds);

    const conf = Math.min(100, Math.max(0, parseFloat(initialConfidence) || 0));
    setBodyConfidence(conf);
    const isDetected = conf >= 70;
    setBodyDetected(isDetected);

    if (!isDetected) {
      setStatus('DETECTING_BODY');
      voiceService.announce('Please stand where your full body is visible.');
    } else {
      setStatus('COUNTDOWN');
      triggerVibration([100]);
      voiceService.announce(`Workout starting in ${seconds}`);
    }
  }, [clearTimer, triggerVibration]);

  // Start 3-second quick resume countdown when unpausing
  const startResumeCountdown = useCallback((seconds = 3) => {
    clearTimer();
    voiceService.stop();
    totalSecondsRef.current = seconds;
    setSecondsLeft(seconds);
    setStatus('COUNTDOWN');
    triggerVibration([100]);
    voiceService.announce(`Resuming in ${seconds}`);
  }, [clearTimer, triggerVibration]);

  // Cancel/stop countdown completely
  const cancelCountdown = useCallback(() => {
    clearTimer();
    voiceService.stop();
    setStatus('IDLE');
  }, [clearTimer]);

  // Main countdown tick interval effect
  useEffect(() => {
    if (status !== 'COUNTDOWN') {
      clearTimer();
      return;
    }

    timerRef.current = setInterval(() => {
      setSecondsLeft(prev => {
        if (prev <= 1) {
          clearTimer();
          setStatus('ACTIVE');
          playGoChime();
          triggerVibration([150, 50, 150]);
          voiceService.announce('Go');
          if (onCompleteRef.current) {
            onCompleteRef.current();
          }
          return 0;
        }

        const nextSec = prev - 1;
        playTickSound();
        triggerVibration([80]);
        voiceService.speakCount(nextSec);
        return nextSec;
      });
    }, 1000);

    return () => clearTimer();
  }, [status, clearTimer, playTickSound, playGoChime, triggerVibration]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      clearTimer();
      voiceService.stop();
      if (audioCtxRef.current) {
        audioCtxRef.current.close().catch(() => {});
      }
    };
  }, [clearTimer]);

  return {
    status,
    secondsLeft,
    totalSeconds: totalSecondsRef.current,
    bodyConfidence,
    bodyDetected,
    exerciseName,
    isMuted,
    startStartCountdown,
    startResumeCountdown,
    cancelCountdown,
    toggleMute,
    updateBodyConfidence,
    setStatus,
  };
}

export default useCountdown;
