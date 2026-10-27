import React from 'react';
import { useWebSocket } from '../context/WebSocketContext';
import { ShieldAlert, AlertTriangle, X, Check, Eye, Smile, Smartphone } from 'lucide-react';
import { formatDateTime } from '../utils/dateUtils';

export default function ToastAlert() {
  const { toastAlert, clearToast, urgentAlert, dismissUrgentAlert } = useWebSocket();

  // 1. High-Priority URGENT SAFETY ALERT takes precedence
  if (urgentAlert) {
    const isCritical = urgentAlert.risk_level === 'CRITICAL';
    const evidence = urgentAlert.evidence || {};
    const ratio = evidence.drowsiness_ratio != null ? Math.round(evidence.drowsiness_ratio * 100) : null;
    const closedSec = evidence.consecutive_closed_sec || evidence.duration;

    return (
      <div className="fixed top-20 right-6 z-50 max-w-lg w-full bg-slate-900 text-white p-5 rounded-2xl shadow-2xl border-2 animate-bounce-short transition-all">
        <div className={`flex items-start gap-3.5 pb-3 border-b ${isCritical ? 'border-rose-700/60' : 'border-amber-700/60'}`}>
          <div className={`p-2.5 rounded-xl shrink-0 ${isCritical ? 'bg-rose-600 text-white shadow-lg shadow-rose-900/50' : 'bg-amber-500 text-slate-950 shadow-lg shadow-amber-900/50'}`}>
            <ShieldAlert className="w-6 h-6 animate-pulse" />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between">
              <span className={`text-[11px] font-black tracking-wider uppercase px-2 py-0.5 rounded ${isCritical ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40' : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'}`}>
                {isCritical ? 'CRITICAL SAFETY ALERT' : 'HIGH RISK ALERT'}
              </span>
              <button
                onClick={() => dismissUrgentAlert(urgentAlert.alert_id)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
                title="Dismiss Alert"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <h4 className="text-base font-bold text-white mt-1.5 truncate">
              {urgentAlert.alert_type ? urgentAlert.alert_type.replace(/_/g, ' ') : 'Sustained Driver Risk'}
            </h4>

            <div className="flex items-center gap-2 text-xs text-slate-300 mt-0.5">
              <span>Driver: <strong className="text-white">{urgentAlert.driver_id || 'DRV001'}</strong></span>
              <span>•</span>
              <span className="text-slate-400 font-mono text-[11px]">{formatDateTime(urgentAlert.timestamp)}</span>
            </div>
          </div>
        </div>

        {/* Evidence Breakdown */}
        <div className="mt-3 bg-slate-800/80 rounded-xl p-3 border border-slate-700/60 text-xs">
          <span className="font-bold text-slate-300 uppercase tracking-wider text-[10px] block mb-1.5">
            Verified Telemetry Evidence
          </span>
          <div className="grid grid-cols-2 gap-2 text-slate-200">
            {ratio != null && (
              <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-750">
                <span className="text-slate-400 text-[10px] block">Drowsiness Ratio</span>
                <span className="font-mono font-bold text-amber-400">{ratio}%</span>
              </div>
            )}
            {closedSec != null && closedSec > 0 && (
              <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-750">
                <span className="text-slate-400 text-[10px] block">Continuous Eye Closure</span>
                <span className="font-mono font-bold text-rose-400">{closedSec}s</span>
              </div>
            )}
            {evidence.recent_drowsiness_count != null && (
              <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-750">
                <span className="text-slate-400 text-[10px] block">Recent Incidents</span>
                <span className="font-mono font-bold text-indigo-300">{evidence.recent_drowsiness_count}</span>
              </div>
            )}
            {evidence.head_pose && (
              <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-750">
                <span className="text-slate-400 text-[10px] block">Head Posture</span>
                <span className="font-mono font-bold text-slate-300">{evidence.head_pose}</span>
              </div>
            )}
          </div>

          {/* Explanation */}
          {urgentAlert.explanation && (
            <p className="mt-2.5 text-slate-300 text-xs leading-relaxed border-t border-slate-700/60 pt-2">
              {urgentAlert.explanation}
            </p>
          )}

          {/* Action Recommendations */}
          {urgentAlert.recommendations && urgentAlert.recommendations.length > 0 && (
            <div className="mt-2 pt-2 border-t border-slate-700/60">
              <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400 block mb-1">
                Recommended Actions:
              </span>
              <ul className="list-disc list-inside space-y-0.5 text-[11px] text-slate-300">
                {urgentAlert.recommendations.slice(0, 2).map((rec, idx) => (
                  <li key={idx} className="truncate">{rec}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-2 mt-3 pt-2">
          <button
            onClick={() => dismissUrgentAlert(urgentAlert.alert_id)}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-colors flex items-center gap-1.5 ${isCritical ? 'bg-rose-600 hover:bg-rose-700 text-white' : 'bg-amber-500 hover:bg-amber-600 text-slate-950'}`}
          >
            <Check className="w-3.5 h-3.5" />
            <span>Acknowledge Alert</span>
          </button>
        </div>
      </div>
    );
  }

  // 2. Ordinary real-time event toast (if active)
  if (!toastAlert) return null;

  const getIcon = (type) => {
    if (type === 'DROWSINESS') return <Eye className="w-5 h-5 text-indigo-400" />;
    if (type === 'YAWNING') return <Smile className="w-5 h-5 text-amber-400" />;
    return <Smartphone className="w-5 h-5 text-rose-400" />;
  };

  const getStatusBadgeColor = (status) => {
    if (status === 'UNSAFE' || status === 'HIGH_RISK') return 'bg-rose-500 text-white';
    if (status === 'ATTENTION_REQUIRED') return 'bg-amber-500 text-white';
    return 'bg-blue-600 text-white';
  };

  return (
    <div className="fixed top-20 right-6 z-40 max-w-md w-full bg-slate-900 text-white p-4 rounded-2xl shadow-2xl border border-slate-700 animate-slide-in flex items-start gap-4">
      <div className="p-2.5 bg-slate-800 rounded-xl border border-slate-700 shrink-0">
        {getIcon(toastAlert.type)}
      </div>

      <div className="flex-1">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            LIVE SAFETY EVENT
          </span>
          <button onClick={clearToast} className="text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        <h4 className="text-sm font-bold text-white mt-1">
          {(toastAlert?.type || 'SAFETY_EVENT').replace(/_/g, ' ')}
        </h4>

        <div className="flex items-center gap-3 mt-2 text-xs">
          <span className="text-slate-300">Duration: <strong>{toastAlert.duration}s</strong></span>
          <span className={`px-2 py-0.5 rounded-md font-bold text-[10px] ${getStatusBadgeColor(toastAlert.status)}`}>
            {toastAlert.status}
          </span>
          <span className="text-slate-400 ml-auto font-mono text-[11px]">{toastAlert.timestamp}</span>
        </div>
      </div>
    </div>
  );
}
