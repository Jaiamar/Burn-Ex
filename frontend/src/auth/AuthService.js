/**
 * src/auth/AuthService.js
 * Burn-Ex — Firebase Authentication Service
 *
 * All authentication logic lives here so UI components stay clean.
 * This module wraps the Firebase Auth SDK with user-friendly error
 * messages and a consistent return shape:
 *
 *   { uid, email, name, photoURL, role, token }
 *
 * Usage:
 *   import { loginWithEmail, loginWithGoogle, logout } from './AuthService';
 */

import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  sendPasswordResetEmail,
  signOut,
  updateProfile,
  onAuthStateChanged,
  GoogleAuthProvider,
} from 'firebase/auth';

import { auth } from '../firebase/firebaseConfig';

export { auth };

// ─── Normalise a Firebase user into the Burn-Ex user shape ────────────────────
// NOTE: 'token' is intentionally NOT stored here.
// Firebase ID tokens expire after 1 hour and must be fetched fresh via
// getIdToken(). Use authenticatedFetch() or getIdToken() directly.
function _mapUser(firebaseUser) {
  if (!firebaseUser) return null;
  return {
    uid:      firebaseUser.uid,
    email:    firebaseUser.email || '',
    name:     firebaseUser.displayName
                || firebaseUser.email?.split('@')[0]
                || 'Athlete',
    photoURL: firebaseUser.photoURL || null,
    role:     'user',
    // No 'token' field — always call getIdToken() on demand.
  };
}

// ─── Convert Firebase error codes → human-readable messages ──────────────────
export function getFirebaseErrorMessage(err) {
  console.error('[BX Auth] Authentication internal error:', err);
  const code = err?.code || '';

  const map = {
    'auth/invalid-credential':          'Invalid email or password.',
    'auth/user-not-found':              'No account found with this email address.',
    'auth/wrong-password':              'Invalid email or password.',
    'auth/invalid-email':               'Please enter a valid email address.',
    'auth/email-already-in-use':        'An account with this email already exists.',
    'auth/weak-password':               'Please choose a stronger password (at least 6 characters).',
    'auth/popup-closed-by-user':        'Google sign-in was cancelled.',
    'auth/cancelled-popup-request':     'Google sign-in was cancelled.',
    'auth/popup-blocked':               'Pop-up was blocked. Please allow pop-ups for this site.',
    'auth/too-many-requests':           'Too many failed attempts. Please try again later.',
    'auth/network-request-failed':      'Network connection failed. Please check your internet.',
    'auth/requires-recent-login':       'Please log in again to continue.',
    'auth/account-exists-with-different-credential':
                                        'An account already exists with the same email using a different sign-in method.',
    'auth/operation-not-allowed':       'This sign-in method is not enabled. Contact support.',
    'auth/user-disabled':               'This account has been disabled. Contact support.',
    'auth/missing-email':               'Please enter your email address.',
  };

  if (map[code]) return map[code];

  // Partial match fallback
  if (code.includes('invalid-credential') || code.includes('wrong-password'))
    return 'Invalid email or password.';
  if (code.includes('user-not-found'))
    return 'No account found with this email address.';
  if (code.includes('email-already-in-use'))
    return 'An account with this email already exists.';
  if (code.includes('popup'))
    return 'Google sign-in was cancelled or blocked.';
  if (code.includes('network'))
    return 'Network error. Please check your connection.';

  // Generic fallback with details if available
  if (err?.message) {
    return `Authentication failed: ${err.message}`;
  }
  return 'An unexpected error occurred. Please try again.';
}

// ─── Auth state observer ──────────────────────────────────────────────────────
/**
 * Subscribe to Firebase auth state changes.
 *
 * @param {(user: BurnExUser | null) => void} callback
 * @returns {() => void} Unsubscribe function
 */
export function onAuthStateChange(callback) {
  return onAuthStateChanged(auth, (firebaseUser) => {
    callback(_mapUser(firebaseUser));
  });
}

// ─── Email / Password ─────────────────────────────────────────────────────────
/**
 * Sign in with email and password.
 * Throws a user-friendly error string on failure.
 */
export async function loginWithEmail(email, password) {
  if (!auth) {
    throw new Error("Firebase Auth is not initialized. Please check your configuration.");
  }
  if (typeof email !== 'string' || !email?.trim()) {
    throw new Error("Email is required and must be a valid string.");
  }
  if (typeof password !== 'string' || !password?.trim()) {
    throw new Error("Password is required and must be a valid string.");
  }

  try {
    const cred = await signInWithEmailAndPassword(auth, email.trim(), password);
    console.log("Login Success:", cred.user);
    return _mapUser(cred.user);
  } catch (error) {
    console.error("Firebase Auth Error:", error);
    console.error("Error Code:", error.code);
    console.error("Error Message:", error.message);
    throw error;
  }
}

/**
 * Create a new account.
 * Optionally sets displayName immediately after creation.
 */
export async function registerWithEmail(email, password, displayName) {
  if (!auth) {
    throw new Error("Firebase Auth is not initialized. Please check your configuration.");
  }
  if (typeof email !== 'string' || !email?.trim()) {
    throw new Error("Email is required and must be a valid string.");
  }
  if (typeof password !== 'string' || !password?.trim()) {
    throw new Error("Password is required and must be a valid string.");
  }

  try {
    const cred = await createUserWithEmailAndPassword(auth, email.trim(), password);
    console.log("Registration Success:", cred.user);
    if (displayName && displayName.trim()) {
      await updateProfile(cred.user, { displayName: displayName.trim() });
      // Refresh the local user object so displayName is visible immediately
      await cred.user.reload();
    }
    return _mapUser({ ...cred.user, displayName: displayName || cred.user.displayName });
  } catch (error) {
    console.error("Firebase Registration Error:", error);
    console.error("Error Code:", error.code);
    console.error("Error Message:", error.message);
    throw error;
  }
}

// ─── Google OAuth ──────────────────────────────────────────────────────────────
/**
 * Open a Google sign-in popup.
 * Returns the authenticated user or throws.
 */
export async function loginWithGoogle() {
  if (!auth) {
    throw new Error("Firebase Auth is not initialized. Please check your configuration.");
  }

  // Create GoogleAuthProvider instance immediately before popup login
  const provider = new GoogleAuthProvider();
  
  // Add required scopes
  provider.addScope('profile');
  provider.addScope('email');

  // Deep diagnostics as required
  console.log("AUTH INSTANCE:", auth);
  console.log("AUTH TYPE:", typeof auth);
  console.log("PROVIDER:", provider);
  console.log({
    auth,
    provider,
    authType: auth?.constructor?.name,
    providerType: provider?.constructor?.name
  });

  try {
    const result = await signInWithPopup(auth, provider);
    console.log("Google Login Success:", result.user);
    return _mapUser(result.user);
  } catch (error) {
    console.error("Firebase Google Auth Error:", error);
    console.error("Error Code:", error.code);
    console.error("Error Message:", error.message);
    throw error;
  }
}

// ─── Forgot Password ──────────────────────────────────────────────────────────
/**
 * Send a password-reset email to the given address.
 */
export async function sendPasswordReset(email) {
  if (!auth) {
    throw new Error("Firebase Auth is not initialized. Please check your configuration.");
  }
  if (typeof email !== 'string' || !email?.trim()) {
    throw new Error("Email is required and must be a valid string.");
  }

  try {
    await sendPasswordResetEmail(auth, email.trim());
    console.log("Password reset email sent to:", email);
    return { success: true };
  } catch (error) {
    console.error("Firebase Password Reset Error:", error);
    console.error("Error Code:", error.code);
    console.error("Error Message:", error.message);
    throw error;
  }
}

// Keep track of any active getIdToken(true) promise to avoid concurrent refreshes
let tokenRefreshPromise = null;

// ─── Get Firebase ID Token ────────────────────────────────────────────────────
/**
 * Get the current Firebase ID token.
 * This is the JWT that the backend verifies with Firebase Admin SDK.
 * Never cache this — Firebase handles refresh automatically.
 *
 * @param {boolean} forceRefresh - Set true to force a new token even if cached.
 * @returns {Promise<string>} The Firebase ID token (JWT).
 */
export async function getIdToken(forceRefresh = false) {
  const user = auth.currentUser;
  if (!user) throw new Error('No authenticated user — cannot get ID token.');
  
  if (forceRefresh) {
    if (!tokenRefreshPromise) {
      tokenRefreshPromise = user.getIdToken(true).finally(() => {
        tokenRefreshPromise = null;
      });
    }
    return tokenRefreshPromise;
  }
  
  return user.getIdToken(false);
}

// ─── Authenticated Fetch ──────────────────────────────────────────────────────
/**
 * Makes an authenticated HTTP request by automatically fetching the
 * current Firebase ID token and attaching it as a Bearer Authorization header.
 *
 * This is the ONLY correct way to call the Burn-Ex backend from the frontend.
 * Never manually build Authorization headers elsewhere.
 *
 * @param {string} url - The API endpoint URL.
 * @param {RequestInit & {forceRefresh?: boolean}} options - Standard fetch options plus forceRefresh.
 * @returns {Promise<Response>} The fetch Response.
 */
export async function authenticatedFetch(url, options = {}) {
  const user = auth.currentUser;
  if (!user) {
    throw new Error('User is not authenticated. Cannot make authenticated request.');
  }

  const { forceRefresh = false, retries = 2, ...fetchOptions } = options;

  // Always get a fresh ID token — Firebase returns the cached one if it is
  // still valid (>5 min remaining) or transparently refreshes it if not.
  const idToken = await getIdToken(forceRefresh);

  const requestHeaders = {
    'Content-Type': 'application/json',
    ...fetchOptions.headers,
    'Authorization': `Bearer ${idToken}`,
  };

  let lastError = null;
  const delays = [1000, 2000, 5000];

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      console.log(`[API] Fetching ${url} (Attempt ${attempt + 1}/${retries + 1})`);
      const response = await fetch(url, {
        ...fetchOptions,
        headers: requestHeaders,
      });

      return response;
    } catch (err) {
      console.warn(`[API Network Error] Attempt ${attempt + 1} failed for ${url}:`, err.message);
      lastError = err;

      if (attempt === retries) {
        break;
      }

      const delayMs = delays[attempt] || 2000;
      console.log(`[Retry] Waiting ${delayMs}ms before attempt ${attempt + 2}...`);
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }

  const networkError = new Error(`Backend server unavailable (ERR_CONNECTION_REFUSED)`);
  networkError.isNetworkError = true;
  networkError.originalError = lastError;
  throw networkError;
}


// ─── Sign Out ─────────────────────────────────────────────────────────────────
/**
 * Sign the current user out from Firebase.
 */
export async function logout() {
  if (!auth) {
    throw new Error("Firebase Auth is not initialized. Please check your configuration.");
  }
  try {
    await signOut(auth);
    console.log("Signout Success");
  } catch (error) {
    console.error("Firebase Signout Error:", error);
    console.error("Error Code:", error.code);
    console.error("Error Message:", error.message);
    throw error;
  }
}

// ─── Convenience: current user (sync) ────────────────────────────────────────
/**
 * Returns the currently authenticated Firebase user, or null.
 * Prefer onAuthStateChange() for reactive updates.
 */
export function getCurrentUser() {
  return _mapUser(auth.currentUser);
}

/**
 * Returns the raw Firebase user object.
 */
export function getRawFirebaseUser() {
  return auth.currentUser;
}

export function isFirebaseEnabled() {
  return true; // Always true — we are using real Firebase
}
