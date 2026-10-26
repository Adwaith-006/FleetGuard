import React, { useEffect, useState } from 'react';
import Header from '../components/Header';
import { fetchEvents, MOCK_DRIVERS, MOCK_VEHICLES } from '../services/dataService';
import { calculateSafetyScore } from '../utils/safetyScore';
import { useWebSocket } from '../context/WebSocketContext';
import { 
  Users, 
  Truck, 
  AlertTriangle, 
  ShieldAlert, 
  Eye, 
  Smile, 
  Smartphone,
  ShieldCheck,
  ArrowRight,
  Radio,
  Clock
} from 'lucide-react';
import { Link } from 'react-router-dom';

export default function Dashboard() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const { isConnected, latestEvent, liveEventsList } = useWebSocket();

  useEffect(() => {
    fetchEvents().then(data => {
      setEvents(data);
      setLoading(false);
    });
  }, []);

  // Merge events from API fetch with new live events arriving over WebSocket
  const mergedEvents = [...liveEventsList, ...events].reduce((acc, current) => {
    const x = acc.find(item => item.event_id === current.event_id);
    if (!x) {
      return acc.concat([current]);
    } else {
      return acc;
    }
  }, []);

  const allCurrentEvents = [...mergedEvents].sort((a, b) => {
    const timeA = new Date(a.start_time || a.timestamp || 0).getTime();
    const timeB = new Date(b.start_time || b.timestamp || 0).getTime();
    return timeB - timeA;
  });

  const totalDrivers = MOCK_DRIVERS.length;
  const totalVehicles = MOCK_VEHICLES.length;
  const totalEvents = allCurrentEvents.length;
  const criticalEvents = allCurrentEvents.filter(
    e => e.severity === 'CRITICAL' || e.status === 'UNSAFE' || e.status === 'HIGH_RISK'
  ).length;

  const drowsinessCount = allCurrentEvents.filter(e => e.event_type === 'DROWSINESS').length;
  const yawningCount = allCurrentEvents.filter(e => e.event_type === 'YAWNING').length;
  const phoneCount = allCurrentEvents.filter(
    e => e.event_type === 'PHONE_DETECTED' || e.event_type === 'PHONE_USAGE'
  ).length;

  const fleetScoreInfo = calculateSafetyScore(allCurrentEvents);

  const getStatusBadgeStyle = (status) => {
    if (status === 'UNSAFE' || status === 'HIGH_RISK' || status === 'CRITICAL') {
      return 'bg-rose-100 text-rose-800 border-rose-200';
    }
    if (status === 'ATTENTION_REQUIRED' || status === 'WARNING') {
      return 'bg-amber-100 text-amber-800 border-amber-200';
    }
    if (status === 'BRIEF' || status === 'OBSERVED' || status === 'DROWSINESS_DETECTED' || status === 'LOW') {
      return 'bg-blue-100 text-blue-800 border-blue-200';
    }
    return 'bg-slate-100 text-slate-700 border-slate-200';
  };

  return (
    <div className="flex-1 bg-slate-50 min-h-screen">
      <Header title="Fleet Safety Overview" subtitle="Real-time vehicle edge AI event monitoring" />

      <main className="p-8 max-w-7xl mx-auto space-y-8">
        
        {/* Live Monitoring Status Banner */}
        <div className="bg-slate-900 text-white rounded-2xl p-6 shadow-xl border border-slate-800 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-indigo-600 flex items-center justify-center text-white shadow-lg shadow-indigo-600/30 shrink-0">
              <Radio className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold">LIVE SAFETY MONITORING</h2>
                <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold ${isConnected ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'}`}>
                  {isConnected ? '● CONNECTED' : '○ CONNECTING...'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1 font-medium">
                Webcam AI detection events broadcast instantly via WebSocket
              </p>
            </div>
          </div>

          {/* Latest Live Event Card */}
          {latestEvent ? (
            <div className="bg-slate-800/80 p-3.5 rounded-xl border border-slate-700 text-xs flex items-center gap-4 shrink-0 max-w-sm">
              <div className="p-2 bg-indigo-950 rounded-lg text-indigo-400">
                <Clock className="w-5 h-5" />
              </div>
              <div>
                <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider block">LATEST EVENT DETECTED</span>
                <span className="font-bold text-white text-sm">{latestEvent.event_type}</span>
                <div className="flex items-center gap-2 mt-0.5 text-[11px] text-slate-300">
                  <span>Duration: <strong>{latestEvent.duration}s</strong></span>
                  <span>•</span>
                  <span className={`font-bold px-1.5 py-0.2 rounded text-[10px] ${getStatusBadgeStyle(latestEvent.status)}`}>
                    {latestEvent.status || 'OBSERVED'}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-xs text-slate-400 font-medium">
              Awaiting live AI webcam detections...
            </div>
          )}
        </div>

        {/* Top KPI Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Drivers</p>
              <h3 className="text-2xl font-black text-slate-800 mt-1">{totalDrivers}</h3>
              <p className="text-[11px] text-emerald-600 font-medium mt-1">Demo Fleet Drivers</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600 border border-indigo-100">
              <Users className="w-6 h-6" />
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Vehicles</p>
              <h3 className="text-2xl font-black text-slate-800 mt-1">{totalVehicles}</h3>
              <p className="text-[11px] text-indigo-600 font-medium mt-1">Demo Fleet Vehicles</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center text-blue-600 border border-blue-100">
              <Truck className="w-6 h-6" />
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Safety Events</p>
              <h3 className="text-2xl font-black text-slate-800 mt-1">{totalEvents}</h3>
              <p className="text-[11px] text-slate-500 font-medium mt-1">Logged by Python AI</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-amber-50 flex items-center justify-center text-amber-600 border border-amber-100">
              <ShieldAlert className="w-6 h-6" />
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Critical Alerts</p>
              <h3 className="text-2xl font-black text-rose-600 mt-1">{criticalEvents}</h3>
              <p className="text-[11px] text-rose-600 font-medium mt-1">Objective Classification</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-rose-50 flex items-center justify-center text-rose-600 border border-rose-100">
              <AlertTriangle className="w-6 h-6" />
            </div>
          </div>

        </div>

        {/* Fleet Score & Event Breakdown Card */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Fleet Safety Score Box */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">Fleet Safety Score</h2>
                <ShieldCheck className="w-5 h-5 text-indigo-600" />
              </div>

              <div className="my-6 text-center">
                <div className="inline-flex items-center justify-center w-28 h-28 rounded-full border-4 border-indigo-500/20 bg-indigo-50/50">
                  <span className="text-4xl font-black text-slate-900">{fleetScoreInfo.score}</span>
                </div>
                <div className="mt-3">
                  <span className={`px-3 py-1 rounded-full text-xs font-bold border ${fleetScoreInfo.color}`}>
                    STATUS: {fleetScoreInfo.status}
                  </span>
                </div>
              </div>
            </div>

            <p className="text-[11px] text-slate-400 text-center font-medium">
              Transparent risk score calculated from objective duration metrics.
            </p>
          </div>

          {/* Event Category Counts */}
          <div className="lg:col-span-2 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
            <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-5">
              Event Breakdown
            </h2>

            <div className="grid grid-cols-3 gap-4">
              <div className="p-4 bg-indigo-50/60 rounded-xl border border-indigo-100 text-center">
                <div className="w-10 h-10 rounded-lg bg-indigo-600 text-white flex items-center justify-center mx-auto mb-2">
                  <Eye className="w-5 h-5" />
                </div>
                <p className="text-xs font-semibold text-slate-600">Drowsiness</p>
                <h4 className="text-2xl font-black text-indigo-950 mt-1">{drowsinessCount}</h4>
                <p className="text-[11px] text-slate-400 mt-1">Eye Closures</p>
              </div>

              <div className="p-4 bg-amber-50/60 rounded-xl border border-amber-100 text-center">
                <div className="w-10 h-10 rounded-lg bg-amber-500 text-white flex items-center justify-center mx-auto mb-2">
                  <Smile className="w-5 h-5" />
                </div>
                <p className="text-xs font-semibold text-slate-600">Yawning</p>
                <h4 className="text-2xl font-black text-amber-950 mt-1">{yawningCount}</h4>
                <p className="text-[11px] text-slate-400 mt-1">Fatigue Signs</p>
              </div>

              <div className="p-4 bg-rose-50/60 rounded-xl border border-rose-100 text-center">
                <div className="w-10 h-10 rounded-lg bg-rose-600 text-white flex items-center justify-center mx-auto mb-2">
                  <Smartphone className="w-5 h-5" />
                </div>
                <p className="text-xs font-semibold text-slate-600">Phone Usage</p>
                <h4 className="text-2xl font-black text-rose-950 mt-1">{phoneCount}</h4>
                <p className="text-[11px] text-slate-400 mt-1">Distractions</p>
              </div>
            </div>
          </div>

        </div>

        {/* Recent Events Table */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="p-6 border-b border-slate-200 flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-slate-800">Recent Safety Events</h2>
              <p className="text-xs text-slate-500">Live AI detections from Python webcam monitor</p>
            </div>
            <Link
              to="/history"
              className="flex items-center gap-1.5 text-xs font-semibold text-indigo-600 hover:text-indigo-800"
            >
              <span>View Full History</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                <tr>
                  <th className="p-4">Date & Time</th>
                  <th className="p-4">Driver</th>
                  <th className="p-4">Vehicle</th>
                  <th className="p-4">Event Type</th>
                  <th className="p-4">Duration</th>
                  <th className="p-4">Objective Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading ? (
                  <tr>
                    <td colSpan="6" className="p-6 text-center text-slate-400">Loading events...</td>
                  </tr>
                ) : allCurrentEvents.length > 0 ? (
                  allCurrentEvents.slice(0, 10).map((evt, idx) => (
                    <tr key={evt.event_id || idx} className="hover:bg-slate-50/80 transition-colors">
                      <td className="p-4 font-medium text-slate-900">
                        {evt.start_time ? new Date(evt.start_time).toLocaleString() : 'N/A'}
                      </td>
                      <td className="p-4 font-semibold text-slate-800">{evt.driver_name || 'Prototype Driver (Demo Test)'}</td>
                      <td className="p-4 text-slate-600">{evt.vehicle_no || 'Prototype Vehicle (Cabin Rig)'}</td>
                      <td className="p-4 font-bold text-slate-800">{evt.event_type}</td>
                      <td className="p-4">{evt.duration}s</td>
                      <td className="p-4">
                        <span className={`px-2.5 py-1 rounded-md text-[11px] font-bold border ${getStatusBadgeStyle(evt.status || evt.severity)}`}>
                          {evt.status || evt.severity || 'OBSERVED'}
                        </span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="6" className="p-8 text-center text-slate-400">
                      No safety events logged yet. Start webcam AI monitoring to stream real driver behaviour events.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

      </main>
    </div>
  );
}
