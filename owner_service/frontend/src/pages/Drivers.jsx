import React, { useEffect, useState } from 'react';
import Header from '../components/Header';
import { fetchDrivers, fetchEvents } from '../services/dataService';
import { calculateSafetyScore } from '../utils/safetyScore';
import { useWebSocket } from '../context/WebSocketContext';
import { UserCheck, ShieldCheck, ArrowRight, Radio } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function Drivers() {
  const [drivers, setDrivers] = useState([]);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const { isConnected, latestEvent, driverStatuses } = useWebSocket();

  const loadData = async () => {
    try {
      const [driversData, eventsData] = await Promise.all([
        fetchDrivers(),
        fetchEvents({ limit: 200 })
      ]);
      setDrivers(driversData || []);
      setEvents(eventsData || []);
    } catch (err) {
      console.warn("Failed to load driver roster:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Real-time event ingestion via WebSocket
  useEffect(() => {
    if (!latestEvent) return;
    setEvents(prev => {
      if (prev.some(e => e.event_id === latestEvent.event_id)) {
        return prev;
      }
      return [latestEvent, ...prev];
    });
  }, [latestEvent]);

  return (
    <div className="flex-1 bg-slate-50 min-h-screen">
      <Header title="Fleet Drivers" subtitle="Registered drivers and individual safety performance" />

      <main className="p-8 max-w-7xl mx-auto space-y-6">
        
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-slate-800">Driver Roster ({drivers.length})</h2>

          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold border ${isConnected ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
            <Radio className="w-3.5 h-3.5 animate-pulse" />
            <span>{isConnected ? 'Real-Time Sync Active' : 'Connecting WebSocket...'}</span>
          </div>
        </div>

        {/* Drivers Grid */}
        {loading ? (
          <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center text-slate-400 text-sm">
            Loading fleet drivers...
          </div>
        ) : drivers.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {drivers.map((driver) => {
              const driverId = driver.driver_id || driver.id;
              const driverName = driver.driver_name || driver.name || 'Prototype Driver';
              const vehicleNo = driver.vehicle_no || 'Cabin Rig';
              const driverEvents = events.filter(e => e.driver_id === driverId || e.driver_name === driverName);
              
              // Prefer backend deterministic score when available
              const score = driver.safety_score !== undefined ? driver.safety_score : calculateSafetyScore(driverEvents).score;
              const statusColor = driver.rating_color || calculateSafetyScore(driverEvents).color;

              const liveStatusInfo = driverStatuses[driverId];
              const currentStatus = liveStatusInfo?.status || driver.status || 'NORMAL';
              const isAlert = currentStatus === 'ALERT' || currentStatus === 'CRITICAL' || currentStatus === 'Drowsy' || currentStatus === 'Head down';

              return (
                <div
                  key={driverId}
                  onClick={() => navigate(`/drivers/${driverId}`)}
                  className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs hover:shadow-md transition-all cursor-pointer group flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 font-bold text-lg">
                          {driverName.charAt(0)}
                        </div>
                        <div>
                          <h3 className="font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
                            {driverName}
                          </h3>
                          <div className="flex items-center gap-2 mt-0.5">
                            <p className="text-xs text-slate-400 font-mono">ID: {driverId}</p>
                            <span className={`px-2 py-0.2 rounded-full text-[10px] font-bold border ${isAlert ? 'bg-rose-100 text-rose-800 border-rose-200' : 'bg-emerald-100 text-emerald-800 border-emerald-200'}`}>
                              {currentStatus}
                            </span>
                          </div>
                        </div>
                      </div>

                      <span className={`px-2.5 py-1 rounded-full text-xs font-bold border ${statusColor}`}>
                        {score}/100
                      </span>
                    </div>

                    <div className="space-y-2 py-3 border-y border-slate-100 text-xs text-slate-600">
                      <div className="flex justify-between">
                        <span className="text-slate-400 font-medium">Assigned Vehicle:</span>
                        <span className="font-semibold text-slate-800">{vehicleNo}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400 font-medium">License / Ref:</span>
                        <span className="font-mono text-slate-700">{driver.license || `LIC-${driverId}`}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400 font-medium">Drowsiness Incidents:</span>
                        <span className="font-semibold text-indigo-700">{driverEvents.filter(e => e.event_type === 'DROWSINESS').length}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400 font-medium">Total Violations:</span>
                        <span className="font-bold text-slate-900">{driverEvents.length} Events</span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 pt-2 flex items-center justify-between text-xs font-semibold text-indigo-600">
                    <span>View Driver Details</span>
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center text-slate-400 text-sm">
            No drivers registered in the fleet.
          </div>
        )}

      </main>
    </div>
  );
}
