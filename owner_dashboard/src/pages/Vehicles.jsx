import React, { useEffect, useState } from 'react';
import Header from '../components/Header';
import { MOCK_VEHICLES, fetchEvents } from '../services/dataService';
import { calculateSafetyScore } from '../utils/safetyScore';
import { Truck, ArrowRight, ShieldCheck, Activity } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function Vehicles() {
  const [events, setEvents] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    fetchEvents().then(setEvents);
  }, []);

  return (
    <div className="flex-1 bg-slate-50 min-h-screen">
      <Header title="Fleet Vehicles" subtitle="Registered vehicles and active edge monitoring status" />

      <main className="p-8 max-w-7xl mx-auto space-y-6">
        
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-slate-800">Fleet Vehicles ({MOCK_VEHICLES.length})</h2>
        </div>

        {/* Vehicles Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {MOCK_VEHICLES.map((vehicle) => {
            const vehicleEvents = events.filter(e => e.vehicle_id === vehicle.id || e.vehicle_no === vehicle.vehicleNo);
            const scoreInfo = calculateSafetyScore(vehicleEvents);

            return (
              <div
                key={vehicle.id}
                onClick={() => navigate(`/vehicles/${vehicle.id}`)}
                className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs hover:shadow-md transition-all cursor-pointer group flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600">
                        <Truck className="w-6 h-6" />
                      </div>
                      <div>
                        <h3 className="font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
                          {vehicle.vehicleNo}
                        </h3>
                        <p className="text-xs text-slate-400 font-mono">ID: {vehicle.id}</p>
                      </div>
                    </div>

                    <span className={`px-2.5 py-1 rounded-full text-xs font-bold border ${scoreInfo.color}`}>
                      {scoreInfo.score}/100
                    </span>
                  </div>

                  <div className="space-y-2 py-3 border-y border-slate-100 text-xs text-slate-600">
                    <div className="flex justify-between">
                      <span className="text-slate-400 font-medium">Model:</span>
                      <span className="font-semibold text-slate-800">{vehicle.model}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400 font-medium">Assigned Driver:</span>
                      <span className="font-semibold text-indigo-600">{vehicle.driverName}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400 font-medium">Status:</span>
                      <span className="px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 font-bold text-[11px]">
                        {vehicle.status}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400 font-medium">Total Events:</span>
                      <span className="font-bold text-slate-900">{vehicleEvents.length} Events</span>
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-2 flex items-center justify-between text-xs font-semibold text-indigo-600">
                  <span>View Vehicle Details</span>
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
