/**
 * src/components/ProfileCompletionGuard.jsx
 * Burn-Ex — Profile Completion Route Guard Component.
 *
 * Enforces strict onboarding & access control:
 *   - Unauthenticated users attempting to access protected routes -> login
 *   - Authenticated users with profile_completed == false -> /complete-profile
 *   - Authenticated users with profile_completed == true attempting to visit /complete-profile -> /dashboard
 */

import React, { useEffect } from 'react';

export function ProfileCompletionGuard({
  auth,
  authLoading,
  profileCompleted,
  profileLoading,
  view,
  setView,
  children
}) {
  useEffect(() => {
    if (authLoading || profileLoading) return;

    // 1. Unauthenticated users attempting to access protected routes -> redirect to login
    if (!auth && view !== 'login' && view !== 'signup') {
      setView('login');
      return;
    }

    // 2. Authenticated user visiting onboarding, but profile is ALREADY completed -> redirect to dashboard
    if (auth && profileCompleted && view === 'complete-profile') {
      console.log('[BX Guard] Profile already completed. Skipping onboarding -> redirecting to dashboard.');
      setView('dashboard');
      return;
    }

    // 3. Authenticated user visiting protected views, but profile is NOT completed -> redirect to complete-profile
    if (auth && !profileCompleted && view !== 'complete-profile' && view !== 'login' && view !== 'signup') {
      console.log('[BX Guard] Profile incomplete. Enforcing onboarding -> redirecting to complete-profile.');
      setView('complete-profile');
      return;
    }
  }, [auth, authLoading, profileCompleted, profileLoading, view, setView]);

  return children;
}

export default ProfileCompletionGuard;
