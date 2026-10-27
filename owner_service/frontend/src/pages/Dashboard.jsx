import React, { useEffect, useState } from 'react';
import Header from '../components/Header';
import { fetchEvents, fetchHealth, fetchDrivers } from '../services/dataService';
import { calculateSafetyScore } from '../utils/safetyScore';
import { formatDateTime } from '../utils/dateUtils';
import { useWebSocket } from '../context/WebSocketContext';
import EventDetailModal from '../components/EventDetailModal';
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
  Clock,
  Database,
  Cpu,
  Server,
  RefreshCw,
  Sparkles,
  CheckCircle2,
  XCircle,
  HelpCircle
} from 'lucide-react';
import { Link } from 'react-router-dom';

export default function Dashboard() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [drivers, setDrivers] = useState([]);
  const [health, setHealth] = useState(null);
  const [healthRefreshing, setHealthRefreshing] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const { isConnected, latestEvent, liveEventsList, latestDriverStatus, driverStatuses } = useWebSocket();

  const loadData = async () => {
    try {
      const [eventsData, driversData, healthData] = await Promise.all([
        fetchEvents({ limit: 100 }),
        fetchDrivers(),
        fetchHealth()
      ]);
      setEvents(eventsData || []);
      setDrivers(driversData || []);
      setHealth(healthData);
    } catch (err) {
      console.warn("Error refreshing dashboard data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(() => {
      fetchHealth().then(setHealth);
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  const refreshHealthNow = async () => {
    setHealthRefreshing(true);
    const h = await fetchHealth();
    setHealth(h);
    setHealthRefreshing(false);
  };

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

  const totalDrivers = drivers.length;
  const uniqueVehicles = new Set(drivers.map(d => d.vehicle_no || d.vehicle_id).filter(Boolean));
  const totalVehicles = uniqueVehicles.size || (drivers.length > 0 ? 1 : 0);
  const totalEvents = allCurrentEvents.length;
  const criticalEvents = allCurrentEvents.filter(
    e => e.severity === 'CRITICAL' || e.status === 'UNSAFE' || e.status === 'HIGH_RISK'
  ).length;

  const drowsinessCount = allCurrentEvents.filter(e => e.event_type === 'DROWSINESS').length;
  const yawningCount = allCurrentEvents.filter(e => e.event_type === 'YAWNING').length;
  const headDownCount = allCurrentEvents.filter(e => e.event_type === 'HEAD_DOWN').length;
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

  const handleRowClick = (evt) => {
    setSelectedEvent(evt);
    setIsModalOpen(true);
  };

  const handleAnalysisUpdated = (eventId, analysis) => {
    setEvents(prev => prev.map(e => {
      if (e.event_id === eventId) {
        return { ...e, ai_analysis: analysis, explanation: analysis.summary };
      }
      return e;
    }));
    if (selectedEvent && selectedEvent.event_id === eventId) {
      setSelectedEvent(prev => ({
        ...prev,
        ai_analysis: analysis,
        explanation: analysis.summary
      }));
    }
  };

  const isMongoConnected = health?.database?.status === 'connected';
  const isAiAvailable = health?.ai?.status === 'available';
  const isBackendHealthy = health?.status === 'healthy' || health?.status === 'degraded';

  return (
    <div className="flex-1 bg-slate-50 min-h-screen">
      <Header title="Fleet Safety Overview" subtitle="Real-time commercial fleet edge AI telemetry & owner supervision" />

      <main className="p-8 max-w-7xl mx-auto space-y-8">
        
        {/* System Services Connectivity Bar */}
        <div className="bg-white rounded-2xl p-4 border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">System Services:</span>
            
            {/* Fleet Server Pill */}
            <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${isBackendHealthy ? 'bg-indigo-50 text-indigo-700 border-indigo-200' : 'bg-rose-50 text-rose-700 border-rose-200'}`}>
              <Server className="w-3.5 h-3.5" />
              <span>Fleet Server: {isBackendHealthy ? 'Online' : 'Reconnecting...'}</span>
            </div>

            {/* Safety Database Pill */}
            <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${isMongoConnected ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-rose-50 text-rose-700 border-rose-200'}`}>
              <Database className="w-3.5 h-3.5" />
              <span>Safety Records: {isMongoConnected ? 'Operational' : 'Disconnected'}</span>
            </div>

            {/* AI Assistant Pill */}
            <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${isAiAvailable ? 'bg-purple-50 text-purple-700 border-purple-200' : 'bg-slate-100 text-slate-600 border-slate-200'}`}>
              <Cpu className="w-3.5 h-3.5" />
              <span>AI Safety Intelligence: {isAiAvailable ? 'Active' : 'Standby'}</span>
            </div>

            {/* Live Stream Pill */}
            <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${isConnected ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
              <Radio className="w-3.5 h-3.5 animate-pulse" />
              <span>Live Stream: {isConnected ? 'Active' : 'Connecting...'}</span>
            </div>
          </div>

          <button
            onClick={refreshHealthNow}
            disabled={healthRefreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold transition-colors disabled:opacity-50"
            title="Refresh system status"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${healthRefreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        {/* Live Monitoring Status Banner */}
        <div className="bg-slate-900 text-white rounded-2xl p-6 shadow-xl border border-slate-800 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-indigo-600 flex items-center justify-center text-white shadow-lg shadow-indigo-600/30 shrink-0">
              <Radio className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold">EDGE WEBCAM SAFETY STREAM</h2>
                <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold ${isConnected ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'}`}>
                  {isConnected ? '● BROADCASTING' : '○ CONNECTING...'}
                </span>
                {latestDriverStatus && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                    Status: {latestDriverStatus.status}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 mt-1 font-medium">
                {latestDriverStatus ? (
                  <span>
                    Driver: <strong className="text-white">{latestDriverStatus.driver_id}</strong> • Mode: <strong className="text-indigo-300">{latestDriverStatus.monitoring_state || 'Monitoring active'}</strong>
                    {latestDriverStatus.metrics?.ear !== undefined && ` • EAR: ${latestDriverStatus.metrics.ear}`}
                    {latestDriverStatus.metrics?.mar !== undefined && ` • MAR: ${latestDriverStatus.metrics.mar}`}
                    {latestDriverStatus.metrics?.posture && ` • Pose: ${latestDriverStatus.metrics.posture}`}
                  </span>
                ) : (
                  <span>Camera AI detections stream live and log to verified safety telemetry</span>
                )}
              </p>
            </div>
          </div>

          {/* Latest Live Event Card */}
          {latestEvent ? (
            <div 
              onClick={() => handleRowClick(latestEvent)}
              className="bg-slate-800/80 hover:bg-slate-800 p-3.5 rounded-xl border border-slate-700 text-xs flex items-center gap-4 shrink-0 max-w-sm cursor-pointer transition-colors"
            >
              <div className="p-2 bg-indigo-950 rounded-lg text-indigo-400">
                <Clock className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider block">LATEST EVENT DETECTED</span>
                  <span className="text-[10px] text-indigo-300 font-semibold underline">Inspect</span>
                </div>
                <span className="font-bold text-white text-sm">{latestEvent.event_type}</span>
                <div className="flex items-center gap-2 mt-0.5 text-[11px] text-slate-300">
                  <span>Duration: <strong>{latestEvent.duration}s</strong></span>
                  <span>•</span>
                  <span className={`font-bold px-1.5 py-0.2 rounded text-[10px] ${getStatusBadgeStyle(latestEvent.status || latestEvent.severity)}`}>
                    {latestEvent.status || latestEvent.severity || 'OBSERVED'}
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
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Fleet Drivers</p>
              <h3 className="text-2xl font-black text-slate-800 mt-1">{totalDrivers}</h3>
              <p className="text-[11px] text-emerald-600 font-medium mt-1">Active Roster</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600 border border-indigo-100">
              <Users className="w-6 h-6" />
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Vehicles</p>
              <h3 className="text-2xl font-black text-slate-800 mt-1">{totalVehicles}</h3>
              <p className="text-[11px] text-indigo-600 font-medium mt-1">Fleet Rig Units</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center text-blue-600 border border-blue-100">
              <Truck className="w-6 h-6" />
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Safety Events</p>
              <h3 className="text-2xl font-black text-slate-800 mt-1">{totalEvents}</h3>
              <p className="text-[11px] text-slate-500 font-medium mt-1">Verified Records</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-amber-50 flex items-center justify-center text-amber-600 border border-amber-100">
              <ShieldAlert className="w-6 h-6" />
            </div>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Critical Alerts</p>
              <h3 className="text-2xl font-black text-rose-600 mt-1">{criticalEvents}</h3>
              <p className="text-[11px] text-rose-600 font-medium mt-1">Objective Severity</p>
            </div>
            <div className="w-12 h-12 rounded-xl bg-rose-50 flex items-center justify-center text-rose-600 border border-rose-100">
              <AlertTriangle className="w-6 h-6" />
            </div>
          </div>

        </div>

        {/* Monitored Drivers Status Strip */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">Monitored Fleet Drivers</h2>
              <p className="text-xs text-slate-500">Real-time driver roster and recent safety event activity</p>
            </div>
            <Link to="/drivers" className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1">
              <span>All Drivers</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {drivers.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {drivers.map((drv) => {
                const driverId = drv.driver_id || drv.id;
                const driverName = drv.driver_name || drv.name || 'Prototype Driver';
                const vehicleNo = drv.vehicle_no || 'Cabin Rig';
                const liveStatusInfo = driverStatuses?.[driverId];
                const status = liveStatusInfo?.status || drv.status || 'NORMAL';
                const isAlert = status === 'HIGH_RISK' || status === 'ATTENTION_REQUIRED' || status === 'Drowsy' || status === 'Head down' || (drv.critical_count && drv.critical_count > 0);

                return (
                  <div key={driverId} className="p-4 rounded-xl border border-slate-200 bg-slate-50/70 hover:bg-slate-50 transition-colors flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-900 text-sm">{driverName}</span>
                        <span className="text-[10px] font-mono text-slate-400">({driverId})</span>
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5">Vehicle: <strong className="text-slate-700">{vehicleNo}</strong></p>
                      <div className="flex items-center gap-2 mt-2 text-[11px]">
                        <span className={`px-2 py-0.5 rounded-md font-bold text-[10px] border ${isAlert ? 'bg-rose-100 text-rose-800 border-rose-200' : 'bg-emerald-100 text-emerald-800 border-emerald-200'}`}>
                          {status}
                        </span>
                        {(drv.total_violations !== undefined || drv.total_events !== undefined) && (
                          <span className="text-slate-500 font-medium">
                            {drv.total_violations !== undefined ? drv.total_violations : drv.total_events} events logged
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-8 text-center text-slate-400 text-xs">
              No drivers registered in the fleet.
            </div>
          )}
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
              Transparent safety score calculated from objective duration metrics and verified telemetry records.
            </p>
          </div>

          {/* Event Category Counts */}
          <div className="lg:col-span-2 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
            <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-5">
              Event Breakdown
            </h2>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
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
                <p className="text-[11px] text-slate-400 mt-1">Mouth Open Events</p>
              </div>

              <div className="p-4 bg-rose-50/60 rounded-xl border border-rose-100 text-center">
                <div className="w-10 h-10 rounded-lg bg-rose-600 text-white flex items-center justify-center mx-auto mb-2">
                  <Smartphone className="w-5 h-5" />
                </div>
                <p className="text-xs font-semibold text-slate-600">Phone Usage</p>
                <h4 className="text-2xl font-black text-rose-950 mt-1">{phoneCount}</h4>
                <p className="text-[11px] text-slate-400 mt-1">Distractions</p>
              </div>

              <div className="p-4 bg-purple-50/60 rounded-xl border border-purple-100 text-center">
                <div className="w-10 h-10 rounded-lg bg-purple-600 text-white flex items-center justify-center mx-auto mb-2">
                  <AlertTriangle className="w-5 h-5" />
                </div>
                <p className="text-xs font-semibold text-slate-600">Head Down</p>
                <h4 className="text-2xl font-black text-purple-950 mt-1">{headDownCount}</h4>
                <p className="text-[11px] text-slate-400 mt-1">Slump / Posture</p>
              </div>
            </div>
          </div>

        </div>

        {/* Recent Events Table with Detail & AI Analysis Trigger */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="p-6 border-b border-slate-200 flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-slate-800">Recent Safety Events</h2>
              <p className="text-xs text-slate-500">Live detections from cabin webcam monitor. Click any event to inspect telemetry or view safety insights.</p>
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
                  <th className="p-4">AI Safety Insight</th>
                  <th className="p-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading ? (
                  <tr>
                    <td colSpan="8" className="p-6 text-center text-slate-400">Loading safety events...</td>
                  </tr>
                ) : allCurrentEvents.length > 0 ? (
                  allCurrentEvents.slice(0, 10).map((evt, idx) => {
                    const hasAi = !!(evt.ai_analysis || evt.explanation);
                    return (
                      <tr 
                        key={evt.event_id || idx} 
                        onClick={() => handleRowClick(evt)}
                        className="hover:bg-slate-50/80 transition-colors cursor-pointer group"
                      >
                        <td className="p-4 font-medium text-slate-900">
                          {formatDateTime(evt.start_time || evt.timestamp)}
                        </td>
                        <td className="p-4 font-semibold text-slate-800">{evt.driver_name || 'Prototype Driver'}</td>
                        <td className="p-4 text-slate-600">{evt.vehicle_no || 'Cabin Rig'}</td>
                        <td className="p-4 font-bold text-slate-800">{evt.event_type}</td>
                        <td className="p-4">{evt.duration}s</td>
                        <td className="p-4">
                          <span className={`px-2.5 py-1 rounded-md text-[11px] font-bold border ${getStatusBadgeStyle(evt.status || evt.severity)}`}>
                            {evt.status || evt.severity || 'OBSERVED'}
                          </span>
                        </td>
                        <td className="p-4">
                          {hasAi ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 text-purple-800 border border-purple-200">
                              <Sparkles className="w-3 h-3" />
                              <span>Analyzed</span>
                            </span>
                          ) : (
                            <span className="text-slate-400 text-[11px]">Ready for AI</span>
                          )}
                        </td>
                        <td className="p-4 text-right">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleRowClick(evt);
                            }}
                            className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 group-hover:text-indigo-800 hover:underline"
                          >
                            <span>Inspect</span>
                            <ArrowRight className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan="8" className="p-8 text-center text-slate-400">
                      No safety events recorded yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

      </main>

      {/* Event Details & On-Demand Gemma AI Analysis Modal */}
      {selectedEvent && (
        <EventDetailModal
          event={selectedEvent}
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onAnalysisUpdated={handleAnalysisUpdated}
        />
      )}
    </div>
  );
}
