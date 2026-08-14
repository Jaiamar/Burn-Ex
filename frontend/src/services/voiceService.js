/**
 * src/services/voiceService.js
 * Burn-Ex — Browser SpeechSynthesis API Voice Guidance Service
 * 
 * Provides clear, non-overlapping English voice guidance during workout
 * start countdowns, position detection prompts, and live voice coaching.
 */

class VoiceService {
  constructor() {
    this.synth = typeof window !== 'undefined' ? window.speechSynthesis : null;
    this.muted = false;
    this.currentUtterance = null;
    this.voice = null;

    if (this.synth) {
      this._loadVoices();
      if (this.synth.onvoiceschanged !== undefined) {
        this.synth.onvoiceschanged = () => this._loadVoices();
      }
    }
  }

  _loadVoices() {
    if (!this.synth) return;
    const voices = this.synth.getVoices();
    // Prefer English voices with natural quality
    this.voice = voices.find(v => v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Samantha') || v.name.includes('Daniel')))
      || voices.find(v => v.lang.startsWith('en'))
      || voices[0] || null;
  }

  setMuted(isMuted) {
    this.muted = Boolean(isMuted);
    if (this.muted) {
      this.stop();
    }
  }

  isMuted() {
    return this.muted;
  }

  stop() {
    if (!this.synth) return;
    try {
      this.synth.cancel();
    } catch (e) {
      console.warn('[BX Voice] Cancel failed:', e);
    }
  }

  speak(text, options = {}) {
    if (!this.synth || this.muted || !text) return;

    // Cancel existing utterance to prevent speech overlap
    this.stop();

    try {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = options.rate || 1.0;
      utterance.pitch = options.pitch || 1.0;
      utterance.volume = options.volume || 1.0;
      utterance.lang = 'en-US';

      if (this.voice) {
        utterance.voice = this.voice;
      }

      this.currentUtterance = utterance;
      this.synth.speak(utterance);
    } catch (e) {
      console.error('[BX Voice] Speech synthesis error:', e);
    }
  }

  /**
   * Crisp digit announcement for countdown ticks
   */
  speakCount(digit) {
    if (this.muted) return;
    // Faster rate for crisp digit timing
    this.speak(String(digit), { rate: 1.1, pitch: 1.05 });
  }

  /**
   * Announcement for workout start/status transitions
   */
  announce(text) {
    if (this.muted) return;
    this.speak(text, { rate: 1.0, pitch: 1.0 });
  }

  /**
   * Real-time AI voice coach feedback during exercise sets
   */
  speakCoach(message) {
    if (this.muted) return;
    this.speak(message, { rate: 1.05, pitch: 1.0 });
  }
}

export const voiceService = new VoiceService();
export default voiceService;
