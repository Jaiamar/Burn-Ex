/**
 * src/hooks/useProfileStatus.js
 * Burn-Ex — Custom React Hook to manage and cache user profile completion status.
 * Prevents duplicate API requests and provides centralized profile state.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { authenticatedFetch } from '../auth/AuthService';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export function useProfileStatus(auth, authLoading) {
  const [profile, setProfile] = useState(null);
  const [profileCompleted, setProfileCompleted] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const fetchedRef = useRef(false);
  const authUidRef = useRef(null);

  const fetchProfileStatus = useCallback(async (force = false) => {
    if (!auth) {
      setProfile(null);
      setProfileCompleted(false);
      setLoading(false);
      fetchedRef.current = false;
      authUidRef.current = null;
      return;
    }

    // Prevent redundant network requests for the same authenticated session unless forced
    if (!force && fetchedRef.current && authUidRef.current === auth.uid) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await authenticatedFetch(`${API_BASE}/api/profile/check`, { method: 'POST' });
      if (!res.ok) {
        throw new Error(`Profile check failed with status ${res.status}`);
      }
      const data = await res.json();
      
      const userProfile = data.profile;
      const isCompleted = Boolean(data.profile_completed || userProfile?.profile_completed);

      setProfile(userProfile);
      setProfileCompleted(isCompleted);
      fetchedRef.current = true;
      authUidRef.current = auth.uid;
    } catch (err) {
      console.error('[BX useProfileStatus] Error checking profile status:', err);
      setError(err.message || 'Error fetching profile status');
    } finally {
      setLoading(false);
    }
  }, [auth]);

  useEffect(() => {
    if (authLoading) return;
    if (auth) {
      if (authUidRef.current !== auth.uid) {
        fetchedRef.current = false;
      }
      fetchProfileStatus();
    } else {
      setProfile(null);
      setProfileCompleted(false);
      setLoading(false);
      fetchedRef.current = false;
      authUidRef.current = null;
    }
  }, [auth, authLoading, fetchProfileStatus]);

  const updateProfileState = useCallback((newProfileData) => {
    setProfile(prev => {
      const updated = { ...prev, ...newProfileData };
      if (typeof newProfileData?.profile_completed !== 'undefined') {
        setProfileCompleted(Boolean(newProfileData.profile_completed));
      }
      return updated;
    });
  }, []);

  return {
    profile,
    profileCompleted,
    loading,
    error,
    refetch: () => fetchProfileStatus(true),
    setProfile: updateProfileState,
  };
}
