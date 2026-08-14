// src/firebase/firebaseConfig.js
// ─────────────────────────────────────────────────────────────────────────────
// Firebase is initialized ONCE here and exported as singletons.
// Import { auth } from this file wherever Firebase Auth is needed.
// Never call initializeApp() more than once in the same app.
// ─────────────────────────────────────────────────────────────────────────────

import { initializeApp, getApp, getApps }   from 'firebase/app';
import { initializeAuth,
         browserLocalPersistence,
         browserPopupRedirectResolver }     from 'firebase/auth';

// ── Project configuration ─────────────────────────────────────────────────────
console.log("[BX Firebase Config] Loaded environment variables:", import.meta.env);

const firebaseConfig = {
  apiKey:            import.meta.env.VITE_FIREBASE_API_KEY            || 'AIzaSyDhDe5j0hVJHdTeSpg3NoBlICDuuCWydC8',
  authDomain:        import.meta.env.VITE_FIREBASE_AUTH_DOMAIN        || 'burn-ex-a4591.firebaseapp.com',
  projectId:         import.meta.env.VITE_FIREBASE_PROJECT_ID         || 'burn-ex-a4591',
  storageBucket:     import.meta.env.VITE_FIREBASE_STORAGE_BUCKET     || 'burn-ex-a4591.firebasestorage.app',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '262946573708',
  appId:             import.meta.env.VITE_FIREBASE_APP_ID             || '1:262946573708:web:3abc613467d4318ba3daa9',
  measurementId:     import.meta.env.VITE_FIREBASE_MEASUREMENT_ID     || 'G-4RRJLNEJVY',
};

// ── Initialize ────────────────────────────────────────────────────────────────
// Prevent duplicate initialization during HMR / Development
const app  = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();

// Use initializeAuth with browserLocalPersistence directly to bypass loading
// indexedDBLocalPersistence which contains a visibilitychange regression
// causing "Database is closing/hidden" error in SDK v1.13.4 (Firebase 12.17.x).
// We include browserPopupRedirectResolver to support popup/redirect oauth flows.
const auth = initializeAuth(app, {
  persistence: browserLocalPersistence,
  popupRedirectResolver: browserPopupRedirectResolver,
});

export { app, auth };
