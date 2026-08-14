/**
 * src/components/ErrorBoundary.jsx
 * Burn-Ex — Global React Error Boundary Component
 * 
 * Catches unhandled React rendering errors, prevents blank white screens,
 * logs detailed diagnostics to console, and provides recovery action buttons.
 */

import React from 'react';
import { AlertTriangle, RefreshCw, Trash2, ShieldAlert } from 'lucide-react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { 
      hasError: false, 
      error: null, 
      errorInfo: null 
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[BX ErrorBoundary Caught]', error, errorInfo);
    this.setState({ errorInfo });
  }

  handleReload = () => {
    window.location.reload();
  };

  handleResetAndReload = () => {
    try {
      localStorage.clear();
      sessionStorage.clear();
    } catch (e) {}
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4 font-sans text-slate-100 select-none">
          <div className="w-full max-w-lg bg-slate-900/90 border border-slate-800 rounded-3xl p-6 shadow-2xl space-y-5 text-center">
            
            <div className="w-14 h-14 bg-red-500/10 border border-red-500/20 rounded-2xl flex items-center justify-center mx-auto text-red-500 shadow-inner">
              <ShieldAlert size={30} />
            </div>

            <div>
              <h1 className="text-xl font-black tracking-tight text-white">Something Went Wrong</h1>
              <p className="text-slate-400 text-xs mt-1.5 font-medium leading-relaxed">
                Burn-Ex caught an unexpected UI error. The error has been logged for analysis.
              </p>
            </div>

            {/* Error Message Snippet */}
            <div className="bg-slate-950/80 p-3.5 rounded-2xl border border-slate-800/80 text-left font-mono text-[11px] text-red-400 overflow-x-auto max-h-36">
              <strong>{this.state.error?.toString() || 'Unknown Error'}</strong>
              {this.state.errorInfo?.componentStack && (
                <pre className="text-[10px] text-slate-500 mt-2 whitespace-pre-wrap">
                  {this.state.errorInfo.componentStack}
                </pre>
              )}
            </div>

            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row gap-3 pt-2">
              <button
                type="button"
                onClick={this.handleReload}
                className="flex-1 py-3 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl shadow-lg shadow-indigo-600/20 transition active:scale-95 flex items-center justify-center gap-2"
              >
                <RefreshCw size={15} />
                Reload Application
              </button>

              <button
                type="button"
                onClick={this.handleResetAndReload}
                className="py-3 px-4 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold text-xs rounded-xl border border-slate-700 transition active:scale-95 flex items-center justify-center gap-2"
              >
                <Trash2 size={15} />
                Reset & Reload
              </button>
            </div>

          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
