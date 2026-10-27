import React, { useState, useEffect } from 'react';
import Header from '../components/Header';
import AiSafetyAssistant from '../components/AiSafetyAssistant';
import { fetchDrivers, fetchEvents } from '../services/dataService';
import { calculateSafetyScore } from '../utils/safetyScore';
import { User, Truck, Sparkles, Shield, AlertCircle } from 'lucide-react';

export default function AiAssistantPage() {
  const [drivers, setDrivers] = useState([]);
  const [selectedDriverId, setSelectedDriverId] = useState('DRV001');
  const [allEvents, setAllEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [driversData, eventsData] = await Promise.all([
          fetchDrivers(),
          fetchEvents({ limit: 200 })
        ]);
        if (Array.isArray(driversData) && driversData.length > 0) {
          setDrivers(driversData);
          setSelectedDriverId(driversData[0].driver_id || driversData[0].id || 'DRV001');
        }
        if (Array.isArray(eventsData)) {
          setAllEvents(eventsData);
        }
      } catch (err) {
        console.warn('Error loading assistant context:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const activeDriver = drivers.find(d => (d.driver_id || d.id) === selectedDriverId) || drivers[0] || {
    id: 'DRV001',
    driver_id: 'DRV001',
    driver_name: 'Prototype Driver (Demo Test)',
    vehicle_no: 'Cabin Rig',
    status: 'ACTIVE'
  };

  const driverId = activeDriver.driver_id || activeDriver.id || 'DRV001';
  const driverName = activeDriver.driver_name || activeDriver.name || 'Prototype Driver (Demo Test)';
  const vehicleNo = activeDriver.vehicle_no || activeDriver.vehicleNo || 'Cabin Rig';

  const driverEvents = (allEvents || []).filter(e => (e.driver_id || e.driverId) === driverId);
  const scoreInfo = activeDriver.safety_score !== undefined
    ? { score: activeDriver.safety_score, status: activeDriver.rating_status || 'SAFE', color: activeDriver.rating_color || 'text-emerald-600 bg-emerald-50 border-emerald-200' }
    : (calculateSafetyScore(driverEvents) || { score: 100, status: 'SAFE', color: 'text-emerald-600 bg-emerald-50 border-emerald-200' });

  return (
    <div className="flex-1 bg-slate-50 min-h-screen">
      <Header
        title="AI Safety Assistant"
        subtitle="Conversational driver safety insights and intelligent fleet risk evaluation"
      />

      <main className="p-8 max-w-7xl mx-auto space-y-6">
        {/* Driver Selection & Context Bar */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center font-bold text-lg shadow-md shadow-indigo-600/30">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <label htmlFor="driver-select" className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
                Select Active Fleet Driver
              </label>
              <div className="flex items-center gap-2 mt-0.5">
                <select
                  id="driver-select"
                  value={selectedDriverId}
                  onChange={(e) => setSelectedDriverId(e.target.value)}
                  className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 text-xs font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  {drivers.map(d => {
                    const dId = d.driver_id || d.id;
                    const dName = d.driver_name || d.name;
                    return (
                      <option key={dId} value={dId}>
                        {dName} ({dId})
                      </option>
                    );
                  })}
                </select>

                <span className="text-xs text-slate-400">•</span>
                <span className="text-xs text-slate-600 font-medium flex items-center gap-1">
                  <Truck className="w-3.5 h-3.5 text-slate-400" />
                  <span>Assigned: <strong>{vehicleNo}</strong></span>
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs">
            <div className="text-right">
              <span className="text-[10px] text-slate-400 uppercase font-bold block">Current Score</span>
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold border ${scoreInfo.color}`}>
                {scoreInfo.score}/100 • {scoreInfo.status}
              </span>
            </div>

            <div className="text-right border-l border-slate-100 pl-4">
              <span className="text-[10px] text-slate-400 uppercase font-bold block">Recorded Violations</span>
              <span className="font-bold text-slate-900 text-sm">{driverEvents.length}</span>
            </div>
          </div>
        </div>

        {/* Gemma AI Assistant Component */}
        <AiSafetyAssistant
          driverId={driverId}
          driverName={driverName}
          vehicleNo={vehicleNo}
          safetyScore={scoreInfo.score}
          totalEvents={driverEvents.length}
          events={driverEvents}
        />
      </main>
    </div>
  );
}
