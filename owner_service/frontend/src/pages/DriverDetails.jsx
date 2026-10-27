import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Header from '../components/Header';
import { fetchEvents, fetchDrivers, fetchDriverById } from '../services/dataService';
import { calculateSafetyScore } from '../utils/safetyScore';
import { formatDateTime } from '../utils/dateUtils';
import { useWebSocket } from '../context/WebSocketContext';
import ReportPreviewModal from '../components/ReportPreviewModal';
import AiSafetyAssistant from '../components/AiSafetyAssistant';
import { 
  ArrowLeft, 
  FileText, 
  ShieldCheck, 
  Eye, 
  Smile, 
  Smartphone, 
  AlertTriangle,
  Radio,
  UserCheck,
  Activity
} from 'lucide-react';

export default function DriverDetails() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [driver, setDriver] = useState(null);
  const [vehicle, setVehicle] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isReportOpen, setIsReportOpen] = useState(false);

  const { isConnected, latestEvent, driverStatuses } = useWebSocket();

  // Initial data loading
  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        let foundDriver = await fetchDriverById(id);
        if (!foundDriver) {
          const allDrivers = await fetchDrivers();
          foundDriver = (allDrivers || []).find(d => (d.driver_id || d.id) === id);
        }
        setDriver(foundDriver || null);

        if (foundDriver) {
          setVehicle({
            id: foundDriver.vehicle_id || 'VEH001',
            vehicleNo: foundDriver.vehicle_no || 'Cabin Rig',
            model: 'Fleet AI Safety Rig'
          });
        }
      } catch (err) {
        console.warn("Failed to load driver details:", err);
      } finally {
        setLoading(false);
      }
    }
    load();

    fetchEvents({ driver_id: id }).then(allEvents => {
      setEvents(allEvents || []);
    });
  }, [id]);

  // Reactive real-time updates via WebSocket
  useEffect(() => {
    if (!latestEvent || !driver) return;
    const targetDriverId = driver.driver_id || driver.id;
    if (latestEvent.driver_id === targetDriverId) {
      setEvents(prev => {
        if (prev.some(e => e.event_id === latestEvent.event_id)) {
          return prev;
        }
        return [latestEvent, ...prev];
      });
    }
  }, [latestEvent, driver]);

  if (loading) {
    return (
      <div className="flex-1 bg-slate-50 min-h-screen flex items-center justify-center">
        <div className="text-slate-400 font-semibold text-sm">Loading driver profile...</div>
      </div>
    );
  }

  if (!driver) {
    return (
      <div className="flex-1 bg-slate-50 min-h-screen flex flex-col items-center justify-center space-y-4">
        <div className="text-slate-500 font-semibold text-sm">Driver profile not found in fleet records.</div>
        <button
          onClick={() => navigate('/drivers')}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-semibold hover:bg-indigo-700 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Return to Drivers</span>
        </button>
      </div>
    );
  }

  const driverId = driver.driver_id || driver.id;
  const driverName = driver.driver_name || driver.name;
  const vehicleNo = driver.vehicle_no || driver.vehicleNo || 'Cabin Rig';
  const liveStatusInfo = driverStatuses[driverId];
  const liveStatusLabel = liveStatusInfo?.status || driver.status || 'NORMAL';
  const liveMonitoringState = liveStatusInfo?.monitoring_state || driver.monitoring_state || (isConnected ? 'Monitoring running normally' : 'Backend disconnected');

  const scoreInfo = calculateSafetyScore(events);
  const drowsinessCount = events.filter(e => e.event_type === 'DROWSINESS').length;
  const yawningCount = events.filter(e => e.event_type === 'YAWNING').length;
  const phoneCount = events.filter(e => e.event_type === 'PHONE_DETECTED' || e.event_type === 'PHONE_USAGE').length;
  const headDownCount = events.filter(e => e.event_type === 'HEAD_DOWN').length;
  const criticalCount = events.filter(e => e.severity === 'CRITICAL').length;

  return (
    <div className="flex-1 bg-slate-50 min-h-screen">
      <Header title={`Driver Profile: ${driverName}`} subtitle={`ID: ${driverId} • Assigned to ${vehicleNo}`} />

      <main className="p-8 max-w-7xl mx-auto space-y-8">
        
        {/* Navigation Back & Action Bar */}
        <div className="flex items-center justify-between">
          <button
            onClick={() => navigate('/drivers')}
            className="flex items-center gap-2 text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Drivers</span>
          </button>

          <div className="flex items-center gap-3">
            {/* Live WebSocket Status Pill */}
            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold border ${isConnected ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
              <Radio className="w-3.5 h-3.5 animate-pulse" />
              <span>{isConnected ? 'Live WebSocket Active' : 'Reconnecting...'}</span>
            </div>

            <button
              onClick={() => setIsReportOpen(true)}
              className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-xl transition-all shadow-md shadow-indigo-600/20"
            >
              <FileText className="w-4 h-4" />
              <span>Generate Report</span>
            </button>
          </div>
        </div>

        {/* Profile Card Header */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs flex flex-wrap items-center justify-between gap-6">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 rounded-2xl bg-indigo-600 text-white flex items-center justify-center font-bold text-2xl shadow-lg shadow-indigo-600/30">
              {driverName.charAt(0)}
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-xl font-bold text-slate-900">{driverName}</h2>
                <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${
                  liveStatusLabel === 'CRITICAL' || liveStatusLabel === 'Drowsy' || liveStatusLabel === 'Head down'
                    ? 'bg-rose-100 text-rose-800 border-rose-200'
                    : liveStatusLabel === 'Yawning' || liveStatusLabel === 'Phone detected'
                    ? 'bg-amber-100 text-amber-800 border-amber-200'
                    : 'bg-emerald-100 text-emerald-800 border-emerald-200'
                }`}>
                  ● {liveStatusLabel}
                </span>
              </div>
              <div className="flex items-center gap-4 text-xs text-slate-500 mt-1 font-medium">
                <span>Driver ID: <strong className="text-slate-800">{driverId}</strong></span>
                <span>•</span>
                <span>Vehicle: <strong className="text-slate-800">{vehicleNo}</strong></span>
                <span>•</span>
                <span>Monitoring State: <strong className="text-indigo-600">{liveMonitoringState}</strong></span>
              </div>
            </div>
          </div>

          <div className="text-right">
            <p className="text-xs text-slate-400 font-semibold uppercase tracking-wider mb-1">Safety Rating</p>
            <span className={`inline-flex items-center px-4 py-1.5 rounded-full text-xs font-bold border ${scoreInfo.color}`}>
              {scoreInfo.status} ({scoreInfo.score}/100)
            </span>
          </div>
        </div>

        {/* Live Camera AI Telemetry Strip */}
        <div className="bg-slate-900 text-white rounded-2xl p-5 border border-slate-800 shadow-md flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white shrink-0 shadow-md shadow-indigo-600/30">
              <Activity className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">Live Edge Camera Stream</span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                  isConnected ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                }`}>
                  {isConnected ? '● BROADCASTING' : '○ RECONNECTING'}
                </span>
                <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${
                  liveStatusLabel === 'Drowsy' || liveStatusLabel === 'Eyes closed' || liveStatusLabel === 'Head down' || liveStatusLabel === 'Head slumped'
                    ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                    : liveStatusLabel === 'Yawning' || liveStatusLabel === 'Mouth open' || liveStatusLabel === 'Phone detected' || liveStatusLabel === 'Phone visible'
                    ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                    : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                }`}>
                  Action: {liveStatusLabel}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Real-time camera telemetry received from vehicle edge AI
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs flex-wrap">
            <div className="bg-slate-800/90 px-3.5 py-1.5 rounded-xl border border-slate-700">
              <span className="text-[10px] text-slate-400 block uppercase font-bold tracking-wider">Live EAR</span>
              <span className="font-mono font-bold text-white text-sm">
                {liveStatusInfo?.metrics?.ear !== undefined ? liveStatusInfo.metrics.ear : '-'}
              </span>
            </div>

            <div className="bg-slate-800/90 px-3.5 py-1.5 rounded-xl border border-slate-700">
              <span className="text-[10px] text-slate-400 block uppercase font-bold tracking-wider">Live MAR</span>
              <span className="font-mono font-bold text-white text-sm">
                {liveStatusInfo?.metrics?.mar !== undefined ? liveStatusInfo.metrics.mar : '-'}
              </span>
            </div>

            <div className="bg-slate-800/90 px-3.5 py-1.5 rounded-xl border border-slate-700">
              <span className="text-[10px] text-slate-400 block uppercase font-bold tracking-wider">Phone Detection</span>
              <span className={`font-bold text-xs ${liveStatusInfo?.metrics?.phone_detected ? 'text-rose-400' : 'text-emerald-400'}`}>
                {liveStatusInfo?.metrics?.phone_detected ? 'DETECTED' : 'CLEAR'}
              </span>
            </div>

            <div className="bg-slate-800/90 px-3.5 py-1.5 rounded-xl border border-slate-700">
              <span className="text-[10px] text-slate-400 block uppercase font-bold tracking-wider">Head Posture</span>
              <span className="font-bold text-xs text-indigo-300">
                {liveStatusInfo?.metrics?.posture || 'UPRIGHT'}
              </span>
            </div>
          </div>
        </div>

        {/* Safety Metrics Grid */}
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
          <div className="bg-white p-4 rounded-xl border border-slate-200 text-center">
            <p className="text-xs font-semibold text-slate-500 uppercase">Total Violations</p>
            <h4 className="text-2xl font-black text-slate-800 mt-1">{events.length}</h4>
          </div>

          <div className="bg-white p-4 rounded-xl border border-slate-200 text-center">
            <p className="text-xs font-semibold text-indigo-600 uppercase">Drowsiness</p>
            <h4 className="text-2xl font-black text-indigo-900 mt-1">{drowsinessCount}</h4>
          </div>

          <div className="bg-white p-4 rounded-xl border border-slate-200 text-center">
            <p className="text-xs font-semibold text-amber-600 uppercase">Yawning</p>
            <h4 className="text-2xl font-black text-amber-900 mt-1">{yawningCount}</h4>
          </div>

          <div className="bg-white p-4 rounded-xl border border-slate-200 text-center">
            <p className="text-xs font-semibold text-rose-600 uppercase">Phone Usage</p>
            <h4 className="text-2xl font-black text-rose-900 mt-1">{phoneCount}</h4>
          </div>

          <div className="bg-white p-4 rounded-xl border border-slate-200 text-center">
            <p className="text-xs font-semibold text-blue-600 uppercase">Head Down</p>
            <h4 className="text-2xl font-black text-blue-900 mt-1">{headDownCount}</h4>
          </div>

          <div className="bg-white p-4 rounded-xl border border-slate-200 text-center">
            <p className="text-xs font-semibold text-purple-600 uppercase">Critical Alerts</p>
            <h4 className="text-2xl font-black text-purple-900 mt-1">{criticalCount}</h4>
          </div>
        </div>

        {/* Gemma AI Safety Assistant Card */}
        <AiSafetyAssistant
          driverId={driverId}
          driverName={driverName}
          vehicleNo={vehicleNo}
          safetyScore={scoreInfo.score}
          totalEvents={events.length}
          events={events}
        />

        {/* Safety Event History Table */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="p-6 border-b border-slate-200 flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-slate-800">Driver Event History</h3>
              <p className="text-xs text-slate-500">Live safety incidents automatically recorded for {driverName}</p>
            </div>
            <span className="text-xs font-medium text-slate-400">
              Showing {events.length} incidents
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                <tr>
                  <th className="p-4">Date & Time</th>
                  <th className="p-4">Event Type</th>
                  <th className="p-4">Duration</th>
                  <th className="p-4">Severity</th>
                  <th className="p-4">Objective Status</th>
                  <th className="p-4">Metrics Logged</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {events.length > 0 ? (
                  events.map((evt, idx) => (
                    <tr key={evt.event_id || idx} className="hover:bg-slate-50 transition-colors">
                      <td className="p-4 font-medium text-slate-900">
                        {formatDateTime(evt.start_time || evt.timestamp)}
                      </td>
                      <td className="p-4 font-bold text-slate-800">{evt.event_type}</td>
                      <td className="p-4">{evt.duration}s</td>
                      <td className="p-4">
                        <span
                          className={`px-2.5 py-1 rounded-full text-[11px] font-bold ${
                            evt.severity === 'CRITICAL'
                              ? 'bg-rose-100 text-rose-700 border border-rose-200'
                              : 'bg-amber-100 text-amber-700 border border-amber-200'
                          }`}
                        >
                          {evt.severity || 'WARNING'}
                        </span>
                      </td>
                      <td className="p-4 font-medium text-slate-600">
                        {evt.status || 'OBSERVED'}
                      </td>
                      <td className="p-4 font-mono text-slate-500">
                        {evt.metrics?.avg_ear
                          ? `avg_ear: ${evt.metrics.avg_ear}`
                          : evt.metrics?.max_mar
                          ? `max_mar: ${evt.metrics.max_mar}`
                          : evt.confidence
                          ? `confidence: ${evt.confidence}`
                          : evt.metrics?.pitch
                          ? `pitch: ${evt.metrics.pitch}`
                          : '-'}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="6" className="p-6 text-center text-slate-400">
                      No safety incidents recorded for this driver.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

      </main>

      <ReportPreviewModal
        isOpen={isReportOpen}
        onClose={() => setIsReportOpen(false)}
        driver={driver}
        vehicle={vehicle}
        events={events}
        dateRange="All Time"
      />
    </div>
  );
}
