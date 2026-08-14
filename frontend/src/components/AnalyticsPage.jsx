/**
 * src/components/AnalyticsPage.jsx
 * Burn-Ex — Calories Analytics & Workout History Dashboard
 * 
 * Features:
 *   - Top summary cards: Calories Today, This Week, Last 15 Days, This Month (with trend % & arrows)
 *   - Date Range Filter: Presets (Today, Yesterday, 7D, 15D, 30D, 90D) & Custom Date Range
 *   - Interactive Calorie Timeline Chart with hover tooltips
 *   - Paginated Workout History Table with Search, Date Sorting, and CSV Export
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { 
  Flame, 
  TrendingUp, 
  TrendingDown, 
  Calendar, 
  Download, 
  Search, 
  ChevronLeft, 
  ChevronRight, 
  Activity, 
  Sparkles, 
  Filter,
  Clock,
  Dumbbell,
  CheckCircle2,
  BarChart3
} from 'lucide-react';
import { authenticatedFetch } from '../auth/AuthService';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export function AnalyticsPage({ auth, history: initialHistory = [] }) {
  // Filter States
  const [filterPreset, setFilterPreset] = useState('15D'); // 'TODAY' | 'YESTERDAY' | '7D' | '15D' | '30D' | '90D' | 'CUSTOM'
  const [customStartDate, setCustomStartDate] = useState('');
  const [customEndDate, setCustomEndDate] = useState('');
  const [activeDateRange, setActiveDateRange] = useState({ start: '', end: '' });

  // Data States
  const [analyticsData, setAnalyticsData] = useState(null);
  const [historyItems, setHistoryItems] = useState([]);
  const [loading, setLoading] = useState(true);

  // Table Search & Pagination States
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [sortOrder, setSortOrder] = useState('desc'); // 'desc' | 'asc'
  const itemsPerPage = 10;

  // Resolve start/end dates from presets
  const resolvePresetDates = useCallback((preset) => {
    const today = new Date();
    const formatDate = (d) => d.toISOString().split('T')[0];
    const end = formatDate(today);

    let start = end;
    if (preset === 'YESTERDAY') {
      const y = new Date(today);
      y.setDate(y.getDate() - 1);
      start = formatDate(y);
      return { start, end: start };
    } else if (preset === '7D') {
      const d = new Date(today);
      d.setDate(d.getDate() - 6);
      start = formatDate(d);
    } else if (preset === '15D') {
      const d = new Date(today);
      d.setDate(d.getDate() - 14);
      start = formatDate(d);
    } else if (preset === '30D') {
      const d = new Date(today);
      d.setDate(d.getDate() - 29);
      start = formatDate(d);
    } else if (preset === '90D') {
      const d = new Date(today);
      d.setDate(d.getDate() - 89);
      start = formatDate(d);
    }
    return { start, end };
  }, []);

  // Fetch analytics data from backend
  const fetchAnalytics = useCallback(async (start, end) => {
    setLoading(true);
    try {
      let url = `${API_BASE}/api/analytics/calories/range?startDate=${start}&endDate=${end}`;
      const res = await authenticatedFetch(url);
      if (res.ok) {
        const data = await res.json();
        setAnalyticsData(data);
      }
    } catch (err) {
      console.error('[BX Analytics] Error fetching analytics:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch history items
  const fetchHistory = useCallback(async (start, end) => {
    try {
      let url = `${API_BASE}/api/analytics/workout-history?startDate=${start}&endDate=${end}&limit=100`;
      const res = await authenticatedFetch(url);
      if (res.ok) {
        const data = await res.json();
        setHistoryItems(data.items || []);
      }
    } catch (err) {
      console.error('[BX Analytics] Error fetching history:', err);
    }
  }, []);

  // Update date range on preset click
  const handlePresetSelect = (preset) => {
    setFilterPreset(preset);
    if (preset !== 'CUSTOM') {
      const dates = resolvePresetDates(preset);
      setActiveDateRange(dates);
      fetchAnalytics(dates.start, dates.end);
      fetchHistory(dates.start, dates.end);
    }
  };

  // Apply custom date range
  const handleApplyCustomRange = () => {
    if (!customStartDate || !customEndDate) return;
    setActiveDateRange({ start: customStartDate, end: customEndDate });
    fetchAnalytics(customStartDate, customEndDate);
    fetchHistory(customStartDate, customEndDate);
  };

  // Initialize data on mount
  useEffect(() => {
    const dates = resolvePresetDates('15D');
    setActiveDateRange(dates);
    fetchAnalytics(dates.start, dates.end);
    fetchHistory(dates.start, dates.end);
  }, [resolvePresetDates, fetchAnalytics, fetchHistory]);

  // Overall metric aggregations for summary cards
  const summaryMetrics = useMemo(() => {
    const todayStr = new Date().toISOString().split('T')[0];
    
    // Today
    const todayKcal = historyItems
      .filter(i => (i.workout_date || "").startsWith(todayStr))
      .reduce((sum, i) => sum + (parseFloat(i.calories_burned) || 0), 0);

    // Last 7 days
    const d7 = new Date(); d7.setDate(d7.getDate() - 6);
    const d7Str = d7.toISOString().split('T')[0];
    const w7Kcal = historyItems
      .filter(i => (i.workout_date || "") >= d7Str)
      .reduce((sum, i) => sum + (parseFloat(i.calories_burned) || 0), 0);

    // Prior 7 days for trend calculation
    const d14 = new Date(); d14.setDate(d14.getDate() - 13);
    const d14Str = d14.toISOString().split('T')[0];
    const prev7Kcal = historyItems
      .filter(i => (i.workout_date || "") >= d14Str && (i.workout_date || "") < d7Str)
      .reduce((sum, i) => sum + (parseFloat(i.calories_burned) || 0), 0);
    const weekTrend = prev7Kcal > 0 ? Math.round(((w7Kcal - prev7Kcal) / prev7Kcal) * 100) : 0;

    // Last 15 days
    const d15 = new Date(); d15.setDate(d15.getDate() - 14);
    const d15Str = d15.toISOString().split('T')[0];
    const w15Kcal = historyItems
      .filter(i => (i.workout_date || "") >= d15Str)
      .reduce((sum, i) => sum + (parseFloat(i.calories_burned) || 0), 0);

    // Last 30 days
    const d30 = new Date(); d30.setDate(d30.getDate() - 29);
    const d30Str = d30.toISOString().split('T')[0];
    const w30Kcal = historyItems
      .filter(i => (i.workout_date || "") >= d30Str)
      .reduce((sum, i) => sum + (parseFloat(i.calories_burned) || 0), 0);

    return {
      today: Math.round(todayKcal),
      week: Math.round(w7Kcal),
      weekTrend,
      fifteenDays: Math.round(w15Kcal),
      month: Math.round(w30Kcal),
    };
  }, [historyItems]);

  // Filtered & Sorted Table Items
  const filteredItems = useMemo(() => {
    let items = [...historyItems];

    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      items = items.filter(i => 
        (i.exercise_name || "").toLowerCase().includes(q) ||
        (i.workout_type || "").toLowerCase().includes(q) ||
        (i.workout_date || "").includes(q)
      );
    }

    items.sort((a, b) => {
      const da = new Date(a.workout_date || a.created_at || 0);
      const db = new Date(b.workout_date || b.created_at || 0);
      return sortOrder === 'desc' ? db - da : da - db;
    });

    return items;
  }, [historyItems, searchTerm, sortOrder]);

  // Pagination slicing
  const totalPages = Math.ceil(filteredItems.length / itemsPerPage) || 1;
  const paginatedItems = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredItems.slice(start, start + itemsPerPage);
  }, [filteredItems, currentPage]);

  // Export Table Data to CSV
  const exportToCsv = () => {
    if (!historyItems.length) return;
    const headers = ['Workout ID', 'Date', 'Workout Type', 'Duration (sec)', 'Calories (kcal)', 'Total Reps', 'Valid Reps', 'Form Score (%)'];
    const rows = historyItems.map(i => [
      i.workout_id || i.session_id || '',
      i.workout_date || '',
      i.exercise_name || i.workout_type || '',
      i.duration_sec || 0,
      i.calories_burned || i.predicted_kcal || 0,
      i.reps_completed || i.total_reps || 0,
      i.valid_reps || 0,
      i.form_score_pct || 100
    ]);

    const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `Burn-Ex-Calories-Analytics-${activeDateRange.start}-to-${activeDateRange.end}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Max value calculation for bar chart scaling
  const chartData = analyticsData?.dailyBreakdown || [];
  const maxCaloriesInChart = Math.max(...chartData.map(d => d.calories || 0), 100);

  return (
    <div className="space-y-6 pb-12 fade-in">
      
      {/* ─── PAGE HEADER ─── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shadow-sm">
              <BarChart3 size={20} />
            </div>
            Calories Analytics & History
          </h1>
          <p className="text-slate-500 text-xs mt-1 font-medium">
            Track historical energy expenditure, workout consistency, and biomechanical metrics across custom date ranges.
          </p>
        </div>

        <button
          onClick={exportToCsv}
          disabled={!historyItems.length}
          className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-bold rounded-xl text-xs flex items-center gap-2 transition active:scale-95 shadow-md shadow-indigo-600/10 self-start md:self-auto"
        >
          <Download size={15} />
          Export CSV Report
        </button>
      </div>

      {/* ─── TOP SUMMARY METRIC CARDS ─── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        
        {/* Card 1: Today */}
        <div className="card-elevated bg-white p-5 rounded-2xl border border-slate-200/70 hover:border-indigo-200 transition">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Calories Today</span>
            <div className="w-8 h-8 rounded-xl bg-orange-50 border border-orange-100 flex items-center justify-center text-orange-500">
              <Flame size={18} />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-black text-slate-900 tracking-tight">{summaryMetrics.today}</span>
            <span className="text-xs font-bold text-slate-400">kcal</span>
          </div>
          <p className="text-[11px] font-semibold text-slate-500 mt-2 flex items-center gap-1">
            <Sparkles size={12} className="text-orange-500" />
            Live burn rate updated
          </p>
        </div>

        {/* Card 2: This Week */}
        <div className="card-elevated bg-white p-5 rounded-2xl border border-slate-200/70 hover:border-indigo-200 transition">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">This Week (7D)</span>
            <div className="w-8 h-8 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
              <Activity size={18} />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-black text-slate-900 tracking-tight">{summaryMetrics.week}</span>
            <span className="text-xs font-bold text-slate-400">kcal</span>
          </div>
          <div className="flex items-center gap-1.5 mt-2">
            {summaryMetrics.weekTrend >= 0 ? (
              <span className="inline-flex items-center text-[10px] font-black text-emerald-600 bg-emerald-50 border border-emerald-100 px-2 py-0.5 rounded-md">
                <TrendingUp size={12} className="mr-0.5" /> +{summaryMetrics.weekTrend}%
              </span>
            ) : (
              <span className="inline-flex items-center text-[10px] font-black text-red-600 bg-red-50 border border-red-100 px-2 py-0.5 rounded-md">
                <TrendingDown size={12} className="mr-0.5" /> {summaryMetrics.weekTrend}%
              </span>
            )}
            <span className="text-[11px] font-semibold text-slate-400">vs previous 7 days</span>
          </div>
        </div>

        {/* Card 3: Last 15 Days */}
        <div className="card-elevated bg-white p-5 rounded-2xl border border-slate-200/70 hover:border-indigo-200 transition">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Last 15 Days</span>
            <div className="w-8 h-8 rounded-xl bg-purple-50 border border-purple-100 flex items-center justify-center text-purple-600">
              <Calendar size={18} />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-black text-slate-900 tracking-tight">{summaryMetrics.fifteenDays}</span>
            <span className="text-xs font-bold text-slate-400">kcal</span>
          </div>
          <p className="text-[11px] font-semibold text-purple-600 mt-2">
            Avg {Math.round(summaryMetrics.fifteenDays / 15)} kcal/day
          </p>
        </div>

        {/* Card 4: This Month */}
        <div className="card-elevated bg-white p-5 rounded-2xl border border-slate-200/70 hover:border-indigo-200 transition">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">This Month (30D)</span>
            <div className="w-8 h-8 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600">
              <Dumbbell size={18} />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-black text-slate-900 tracking-tight">{summaryMetrics.month}</span>
            <span className="text-xs font-bold text-slate-400">kcal</span>
          </div>
          <p className="text-[11px] font-semibold text-emerald-600 mt-2">
            Total monthly energy burn
          </p>
        </div>

      </div>

      {/* ─── DATE FILTER CONTROL BAR ─── */}
      <div className="card-elevated bg-white p-4 rounded-2xl border border-slate-200/70 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          
          {/* Preset Buttons */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-xs font-bold text-slate-400 mr-2 flex items-center gap-1">
              <Filter size={14} /> Filter Range:
            </span>
            {[
              { id: 'TODAY', label: 'Today' },
              { id: 'YESTERDAY', label: 'Yesterday' },
              { id: '7D', label: 'Last 7 Days' },
              { id: '15D', label: 'Last 15 Days' },
              { id: '30D', label: 'Last 30 Days' },
              { id: '90D', label: 'Last 90 Days' },
              { id: 'CUSTOM', label: 'Custom Range' },
            ].map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => handlePresetSelect(p.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                  filterPreset === p.id
                    ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/20'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Active Date Indicator */}
          <div className="text-xs font-bold text-slate-500 bg-slate-50 px-3 py-1.5 rounded-xl border border-slate-200/60 self-start md:self-auto">
            📅 {activeDateRange.start || 'Start'} &mdash; {activeDateRange.end || 'End'}
          </div>
        </div>

        {/* Custom Range Inputs (visible when Custom is selected) */}
        {filterPreset === 'CUSTOM' && (
          <div className="flex items-center gap-3 pt-3 border-t border-slate-100 flex-wrap animate-in fade-in">
            <div className="flex items-center gap-2">
              <label className="text-xs font-bold text-slate-600">Start Date:</label>
              <input
                type="date"
                value={customStartDate}
                onChange={(e) => setCustomStartDate(e.target.value)}
                className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-800 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs font-bold text-slate-600">End Date:</label>
              <input
                type="date"
                value={customEndDate}
                onChange={(e) => setCustomEndDate(e.target.value)}
                className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-800 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <button
              type="button"
              onClick={handleApplyCustomRange}
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl shadow-md transition"
            >
              Apply Filter
            </button>
          </div>
        )}
      </div>

      {/* ─── CALORIE TIMELINE VISUAL CHART ─── */}
      <div className="card-elevated bg-white p-6 rounded-2xl border border-slate-200/70 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-black text-slate-900">Daily Calorie Burn Breakdown</h2>
            <p className="text-slate-500 text-xs mt-0.5 font-medium">Interactive timeline visualization for the active date filter</p>
          </div>
          <div className="flex items-center gap-4 text-xs font-bold text-slate-500">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-md bg-gradient-to-t from-indigo-600 to-purple-500 inline-block" /> Calories (kcal)
            </span>
          </div>
        </div>

        {/* Visual Bar Chart */}
        <div className="h-64 flex items-end gap-2 pt-8 pb-4 border-b border-slate-100 overflow-x-auto">
          {loading ? (
            <div className="w-full h-full flex items-center justify-center text-slate-400 text-xs font-semibold">
              Loading calorie breakdown chart...
            </div>
          ) : chartData.length === 0 ? (
            <div className="w-full h-full flex items-center justify-center text-slate-400 text-xs font-semibold">
              No workout logs found for this date range.
            </div>
          ) : (
            chartData.map((d, idx) => {
              const heightPct = Math.max(10, Math.min(100, (d.calories / maxCaloriesInChart) * 100));
              return (
                <div key={idx} className="flex-1 min-w-[32px] flex flex-col items-center gap-2 group relative">
                  
                  {/* Tooltip on Hover */}
                  <div className="absolute bottom-full mb-2 hidden group-hover:flex flex-col items-center z-20 pointer-events-none">
                    <div className="bg-slate-900 text-white text-[10px] font-bold px-3 py-1.5 rounded-xl shadow-xl whitespace-nowrap">
                      <div>{d.date}</div>
                      <div className="text-orange-400">{d.calories} kcal</div>
                      <div className="text-slate-400">{d.workouts} workouts ({d.reps} reps)</div>
                    </div>
                    <div className="w-2 h-2 bg-slate-900 rotate-45 -mt-1" />
                  </div>

                  {/* Bar */}
                  <div className="w-full bg-slate-100 rounded-xl overflow-hidden flex flex-col justify-end h-44">
                    <div 
                      className="w-full bg-gradient-to-t from-indigo-600 to-purple-500 rounded-xl transition-all duration-500 group-hover:brightness-110"
                      style={{ height: `${heightPct}%` }}
                    />
                  </div>

                  {/* Label */}
                  <span className="text-[10px] font-bold text-slate-400 truncate w-full text-center">
                    {d.date.slice(5)}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* ─── WORKOUT HISTORY TABLE ─── */}
      <div className="card-elevated bg-white p-6 rounded-2xl border border-slate-200/70 space-y-4">
        
        {/* Table Header & Controls */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-black text-slate-900">Detailed Workout Logs</h2>
            <p className="text-slate-500 text-xs mt-0.5 font-medium">View, search, and audit all recorded workouts</p>
          </div>

          <div className="flex items-center gap-3">
            {/* Search Input */}
            <div className="relative">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search exercise or date..."
                value={searchTerm}
                onChange={(e) => { setSearchTerm(e.target.value); setCurrentPage(1); }}
                className="pl-9 pr-4 py-2 bg-slate-50 border border-slate-200/80 rounded-xl text-xs font-semibold text-slate-800 placeholder-slate-400 focus:outline-none focus:border-indigo-500 transition w-56"
              />
            </div>

            {/* Sort Toggle */}
            <button
              onClick={() => setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc')}
              className="px-3 py-2 bg-slate-50 border border-slate-200/80 hover:bg-slate-100 text-slate-600 font-bold rounded-xl text-xs transition"
            >
              Date: {sortOrder === 'desc' ? 'Newest First' : 'Oldest First'}
            </button>
          </div>
        </div>

        {/* History Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200/80 text-[11px] font-black uppercase text-slate-400 tracking-wider">
                <th className="py-3 px-4">Date</th>
                <th className="py-3 px-4">Workout Type</th>
                <th className="py-3 px-4">Duration</th>
                <th className="py-3 px-4 text-right">Calories (kcal)</th>
                <th className="py-3 px-4 text-center">Completed Reps</th>
                <th className="py-3 px-4 text-center">Form Score</th>
                <th className="py-3 px-4 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs font-medium">
              {paginatedItems.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-400 font-semibold">
                    No workout records match your filter criteria.
                  </td>
                </tr>
              ) : (
                paginatedItems.map((item, idx) => {
                  const durationMin = Math.round((item.duration_sec || 0) / 60);
                  const kcal = Math.round(item.calories_burned || item.predicted_kcal || 0);
                  const valid = item.valid_reps || 0;
                  const total = item.reps_completed || item.total_reps || 0;
                  const formScore = Math.round(item.form_score_pct || 100);

                  return (
                    <tr key={idx} className="hover:bg-slate-50/70 transition">
                      <td className="py-3.5 px-4 font-bold text-slate-800">
                        {item.workout_date || (item.created_at || "").slice(0, 10)}
                      </td>
                      <td className="py-3.5 px-4">
                        <span className="font-bold text-slate-900 block">
                          {item.exercise_name || (item.workout_type || "Workout").replace('_', ' ').toUpperCase()}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-slate-600 flex items-center gap-1.5">
                        <Clock size={13} className="text-slate-400" />
                        {durationMin > 0 ? `${durationMin} mins` : `${item.duration_sec || 30} secs`}
                      </td>
                      <td className="py-3.5 px-4 text-right font-black text-orange-600">
                        {kcal} kcal
                      </td>
                      <td className="py-3.5 px-4 text-center font-bold text-slate-800">
                        {valid} / {total} reps
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <span className={`inline-block px-2.5 py-1 rounded-lg text-[10px] font-black ${
                          formScore >= 85 ? 'bg-emerald-50 text-emerald-600 border border-emerald-100' : 'bg-amber-50 text-amber-600 border border-amber-100'
                        }`}>
                          {formScore}%
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-600 bg-emerald-50 border border-emerald-100 px-2.5 py-1 rounded-lg">
                          <CheckCircle2 size={12} /> Logged
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="flex items-center justify-between pt-4 border-t border-slate-100 text-xs font-semibold text-slate-500">
          <span>
            Showing {filteredItems.length > 0 ? (currentPage - 1) * itemsPerPage + 1 : 0} to {Math.min(currentPage * itemsPerPage, filteredItems.length)} of {filteredItems.length} records
          </span>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
              disabled={currentPage === 1}
              className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 disabled:opacity-40 transition"
            >
              <ChevronLeft size={16} />
            </button>
            <span>Page {currentPage} of {totalPages}</span>
            <button
              onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
              disabled={currentPage === totalPages}
              className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 disabled:opacity-40 transition"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>

      </div>

    </div>
  );
}

export default AnalyticsPage;
