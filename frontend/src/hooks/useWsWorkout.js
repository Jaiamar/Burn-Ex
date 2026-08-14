/**
 * src/hooks/useWsWorkout.js
 * Burn-Ex — Server-Side Real-Time WebSocket AI Workout Pipeline Hook
 * 
 * Captures user camera frames, compresses them, streams them to the FastAPI
 * WebSocket server, and updates the local telemetry state.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { getIdToken } from '../auth/AuthService';

export function useWsWorkout() {
  const [connectionStatus, setConnectionStatus] = useState('DISCONNECTED'); // DISCONNECTED, CONNECTING, CONNECTED, PROCESSING
  const [telemetry, setTelemetry] = useState(null);
  const [summary, setSummary] = useState(null);

  const socketRef = useRef(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const intervalIdRef = useRef(null);
  const isProcessingFrameRef = useRef(false);

  // Stop camera and release tracks
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      console.log("[BX WS Hook] Releasing user camera...");
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }, []);

  // Clean up socket and intervals
  const cleanup = useCallback(() => {
    console.log("[BX WS Hook] Cleaning up WebSocket streaming session...");
    if (intervalIdRef.current) {
      clearInterval(intervalIdRef.current);
      intervalIdRef.current = null;
    }
    stopCamera();
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    isProcessingFrameRef.current = false;
  }, [stopCamera]);

  // Connect to backend WebSocket endpoint
  const startWorkout = useCallback(async (videoElement, exerciseType) => {
    cleanup();
    setConnectionStatus('CONNECTING');
    setSummary(null);
    setTelemetry(null);

    videoRef.current = videoElement;
    if (!canvasRef.current) {
      canvasRef.current = document.createElement('canvas');
      canvasRef.current.width = 640;
      canvasRef.current.height = 480;
    }

    try {
      // 1. Capture local webcam feed
      console.log("[BX WS Hook] Activating user camera...");
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, frameRate: { ideal: 30 } },
        audio: false
      });
      streamRef.current = stream;
      if (videoElement) {
        videoElement.srcObject = stream;
        videoElement.play().catch(e => console.log("Play local camera failed:", e));
      }

      // 2. Fetch fresh Firebase ID Token for authentication
      console.log("[BX WS Hook] Fetching Firebase ID token for authentication...");
      const token = await getIdToken(false);

      // 3. Establish WebSocket connection
      // Note: Use ws:// for HTTP development and wss:// for HTTPS production
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = 'localhost:8000'; // FastAPI backend location
      const socketUrl = `${protocol}//${host}/ws/live-workout?token=${encodeURIComponent(token)}`;
      
      console.log("[BX WS Hook] Connecting to WebSocket server:", `${protocol}//${host}/ws/live-workout`);
      const socket = new WebSocket(socketUrl);
      socketRef.current = socket;

      // Offscreen canvas setup
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');

      socket.onopen = () => {
        console.log("[BX WS Hook] WebSocket connection established.");
        setConnectionStatus('CONNECTED');

        // Send start command
        socket.send(JSON.stringify({ type: 'start', exercise: exerciseType }));

        // Start frame capture and transmission interval (Throttled to 130ms ~8 FPS)
        intervalIdRef.current = setInterval(() => {
          if (socket.readyState !== WebSocket.OPEN) return;
          if (isProcessingFrameRef.current) {
            // Backpressure check: Backend is busy processing the previous frame. Skipping frame.
            return;
          }

          if (videoElement && videoElement.readyState === videoElement.HAVE_ENOUGH_DATA) {
            // Draw current frame to offscreen canvas
            ctx.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
            
            // Compress canvas to JPEG blob and send as binary message
            canvas.toBlob((blob) => {
              if (blob && socket.readyState === WebSocket.OPEN) {
                isProcessingFrameRef.current = true;
                setConnectionStatus('PROCESSING');
                socket.send(blob);
              }
            }, 'image/jpeg', 0.6); // 0.6 quality keeps frame payload small and fast
          }
        }, 130);
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'summary') {
            console.log("[BX WS Hook] Received workout final summary:", data.summary);
            setSummary(data.summary);
            cleanup();
            setConnectionStatus('DISCONNECTED');
          } else {
            // Telemetry update received
            setTelemetry(data);
            isProcessingFrameRef.current = false;
            setConnectionStatus('CONNECTED');
          }
        } catch (err) {
          console.error("[BX WS Hook] Message parse error:", err);
        }
      };

      socket.onerror = (err) => {
        console.error("[BX WS Hook] WebSocket connection error:", err);
        setConnectionStatus('DISCONNECTED');
        cleanup();
      };

      socket.onclose = (event) => {
        console.log("[BX WS Hook] WebSocket connection closed.", event.reason);
        setConnectionStatus('DISCONNECTED');
        cleanup();
      };

    } catch (err) {
      console.error("[BX WS Hook] Failed to initialize live streaming session:", err);
      setConnectionStatus('DISCONNECTED');
      cleanup();
    }
  }, [cleanup]);

  const pauseWorkout = useCallback((isPaused) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      console.log("[BX WS Hook] Sending pause command, paused =", isPaused);
      socketRef.current.send(JSON.stringify({ type: 'pause', is_paused: isPaused }));
    }
  }, []);

  const resetWorkout = useCallback(() => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      console.log("[BX WS Hook] Sending reset command...");
      socketRef.current.send(JSON.stringify({ type: 'reset' }));
    }
  }, []);

  const endWorkout = useCallback(() => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      console.log("[BX WS Hook] Sending end workout command...");
      socketRef.current.send(JSON.stringify({ type: 'end' }));
    } else {
      cleanup();
      setConnectionStatus('DISCONNECTED');
    }
  }, [cleanup]);

  // Cleanup on unmount
  useEffect(() => {
    return () => cleanup();
  }, [cleanup]);

  return {
    connectionStatus,
    telemetry,
    summary,
    startWorkout,
    pauseWorkout,
    resetWorkout,
    endWorkout,
    cleanup
  };
}
