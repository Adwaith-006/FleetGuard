import React from 'react';
import { Bell, Activity, Wifi, WifiOff } from 'lucide-react';
import { useWebSocket } from '../context/WebSocketContext';

export default function Header({ title, subtitle }) {
  const { isConnected } = useWebSocket();

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-8 flex items-center justify-between sticky top-0 z-10 shadow-xs">
      <div>
        <h1 className="text-xl font-bold text-slate-800 leading-tight">{title}</h1>
        {subtitle && <p className="text-xs text-slate-500 font-medium">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-4">
        {isConnected ? (
          <div className="flex items-center gap-2 px-3.5 py-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full text-xs font-semibold">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <Wifi className="w-3.5 h-3.5" />
            <span>● Connected to AI Engine</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 px-3.5 py-1.5 bg-amber-50 text-amber-700 border border-amber-200 rounded-full text-xs font-semibold">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-ping"></span>
            <WifiOff className="w-3.5 h-3.5" />
            <span>○ Connecting to Backend...</span>
          </div>
        )}

        <button className="p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors relative">
          <Bell className="w-5 h-5" />
          {isConnected && <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-indigo-600 rounded-full"></span>}
        </button>
      </div>
    </header>
  );
}
