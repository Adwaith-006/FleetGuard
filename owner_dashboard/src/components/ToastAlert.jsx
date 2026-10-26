import React from 'react';
import { useWebSocket } from '../context/WebSocketContext';
import { ShieldAlert, X, Eye, Smile, Smartphone } from 'lucide-react';

export default function ToastAlert() {
  const { toastAlert, clearToast } = useWebSocket();

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
    <div className="fixed top-20 right-6 z-50 max-w-md w-full bg-slate-900 text-white p-4 rounded-2xl shadow-2xl border border-slate-700 animate-slide-in flex items-start gap-4">
      <div className="p-2.5 bg-slate-800 rounded-xl border border-slate-700 shrink-0">
        {getIcon(toastAlert.type)}
      </div>

      <div className="flex-1">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            LIVE SAFETY EVENT DETECTED
          </span>
          <button onClick={clearToast} className="text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        <h4 className="text-sm font-bold text-white mt-1">
          {toastAlert.type.replace('_', ' ')}
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
