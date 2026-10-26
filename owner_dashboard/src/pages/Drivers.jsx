import React, { useEffect, useState } from 'react';
import Header from '../components/Header';
import { MOCK_DRIVERS, fetchEvents } from '../services/dataService';
import { calculateSafetyScore } from '../utils/safetyScore';
import { UserCheck, ShieldCheck, ArrowRight, Phone, Award } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function Drivers() {
  const [events, setEvents] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    fetchEvents().then(setEvents);
  }, []);

  return (
    <div className="flex-1 bg-slate-50 min-h-screen">
      <Header title="Fleet Drivers" subtitle="Registered drivers and individual safety performance" />

      <main className="p-8 max-w-7xl mx-auto space-y-6">
        
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-slate-800">Driver Roster ({MOCK_DRIVERS.length})</h2>
        </div>

        {/* Drivers Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {MOCK_DRIVERS.map((driver) => {
            const driverEvents = events.filter(e => e.driver_id === driver.id || e.driver_name === driver.name);
            const scoreInfo = calculateSafetyScore(driverEvents);

            return (
              <div
                key={driver.id}
                onClick={() => navigate(`/drivers/${driver.id}`)}
                className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs hover:shadow-md transition-all cursor-pointer group flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 font-bold text-lg">
                        {driver.name.charAt(0)}
                      </div>
                      <div>
                        <h3 className="font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
                          {driver.name}
                        </h3>
                        <p className="text-xs text-slate-400 font-mono">ID: {driver.id}</p>
                      </div>
                    </div>

                    <span className={`px-2.5 py-1 rounded-full text-xs font-bold border ${scoreInfo.color}`}>
                      {scoreInfo.score}/100
                    </span>
                  </div>

                  <div className="space-y-2 py-3 border-y border-slate-100 text-xs text-slate-600">
                    <div className="flex justify-between">
                      <span className="text-slate-400 font-medium">Assigned Vehicle:</span>
                      <span className="font-semibold text-slate-800">{driver.vehicleNo}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400 font-medium">License No:</span>
                      <span className="font-mono text-slate-700">{driver.license}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400 font-medium">Experience:</span>
                      <span>{driver.experience}</span>
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

      </main>
    </div>
  );
}
