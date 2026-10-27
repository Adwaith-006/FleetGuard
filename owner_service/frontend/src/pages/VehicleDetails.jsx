import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Header from '../components/Header';
import { fetchVehicles, fetchDrivers, fetchEvents } from '../services/dataService';
import { calculateSafetyScore } from '../utils/safetyScore';
import { formatDateTime } from '../utils/dateUtils';
import ReportPreviewModal from '../components/ReportPreviewModal';
import { ArrowLeft, FileText, Truck } from 'lucide-react';

export default function VehicleDetails() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [vehicle, setVehicle] = useState(null);
  const [driver, setDriver] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isReportOpen, setIsReportOpen] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [vehiclesList, driversList, allEvents] = await Promise.all([
          fetchVehicles(),
          fetchDrivers(),
          fetchEvents()
        ]);
        const foundVehicle = vehiclesList.find(v => v.id === id);
        setVehicle(foundVehicle || null);

        if (foundVehicle) {
          const foundDriver = driversList.find(d => (d.driver_id || d.id) === foundVehicle.driverId);
          setDriver(foundDriver || null);
          const filtered = allEvents.filter(e => e.vehicle_id === foundVehicle.id || e.vehicle_no === foundVehicle.vehicleNo);
          setEvents(filtered);
        }
      } catch (err) {
        console.warn("Failed to load vehicle details:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  if (loading) {
    return (
      <div className="flex-1 bg-slate-50 min-h-screen flex items-center justify-center">
        <div className="text-slate-400 font-semibold text-sm">Loading vehicle details...</div>
      </div>
    );
  }

  if (!vehicle) {
    return (
      <div className="flex-1 bg-slate-50 min-h-screen flex flex-col items-center justify-center space-y-4">
        <div className="text-slate-500 font-semibold text-sm">Vehicle not found in fleet records.</div>
        <button
          onClick={() => navigate('/vehicles')}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-semibold hover:bg-indigo-700 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Return to Vehicles</span>
        </button>
      </div>
    );
  }

  const scoreInfo = calculateSafetyScore(events);
  const drowsinessCount = events.filter(e => e.event_type === 'DROWSINESS').length;
  const yawningCount = events.filter(e => e.event_type === 'YAWNING').length;
  const phoneCount = events.filter(e => e.event_type === 'PHONE_DETECTED' || e.event_type === 'PHONE_USAGE').length;
  const criticalCount = events.filter(e => e.severity === 'CRITICAL').length;

  return (
    <div className="flex-1 bg-slate-50 min-h-screen">
      <Header title={`Vehicle Details: ${vehicle.vehicleNo}`} subtitle={`ID: ${vehicle.id} • Assigned Driver: ${vehicle.driverName || 'Prototype Driver'}`} />

      <main className="p-8 max-w-7xl mx-auto space-y-8">
        
        {/* Navigation & Action */}
        <div className="flex items-center justify-between">
          <button
            onClick={() => navigate('/vehicles')}
            className="flex items-center gap-2 text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Vehicles</span>
          </button>

          <button
            onClick={() => setIsReportOpen(true)}
            className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-xl transition-all shadow-md shadow-indigo-600/20"
          >
            <FileText className="w-4 h-4" />
            <span>Generate Vehicle Report</span>
          </button>
        </div>

        {/* Profile Card Header */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs flex items-center justify-between">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 rounded-2xl bg-blue-600 text-white flex items-center justify-center font-bold text-2xl shadow-lg shadow-blue-600/30">
              <Truck className="w-8 h-8" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-900">{vehicle.vehicleNo}</h2>
              <div className="flex items-center gap-4 text-xs text-slate-500 mt-1 font-medium">
                <span>Vehicle ID: <strong className="text-slate-800">{vehicle.id}</strong></span>
                <span>•</span>
                <span>Model: <strong className="text-slate-800">{vehicle.model}</strong></span>
                <span>•</span>
                <span>Driver: <strong className="text-indigo-600">{vehicle.driverName || 'Prototype Driver'}</strong></span>
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

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
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
            <p className="text-xs font-semibold text-purple-600 uppercase">Critical Alerts</p>
            <h4 className="text-2xl font-black text-purple-900 mt-1">{criticalCount}</h4>
          </div>
        </div>

        {/* Event History Table */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="p-6 border-b border-slate-200">
            <h3 className="text-base font-bold text-slate-800">Vehicle Incident History</h3>
            <p className="text-xs text-slate-500">All recorded safety incidents for vehicle {vehicle.vehicleNo}</p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                <tr>
                  <th className="p-4">Date & Time</th>
                  <th className="p-4">Driver</th>
                  <th className="p-4">Event Type</th>
                  <th className="p-4">Duration</th>
                  <th className="p-4">Severity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {events.length > 0 ? (
                  events.map((evt, idx) => (
                    <tr key={evt.event_id || idx} className="hover:bg-slate-50">
                      <td className="p-4 font-medium text-slate-900">
                        {formatDateTime(evt.start_time || evt.timestamp)}
                      </td>
                      <td className="p-4 font-semibold text-slate-800">{evt.driver_name || vehicle.driverName}</td>
                      <td className="p-4 font-bold text-slate-800">{evt.event_type}</td>
                      <td className="p-4">{evt.duration}s</td>
                      <td className="p-4">
                        <span
                          className={`px-2.5 py-1 rounded-full text-[11px] font-bold ${
                            evt.severity === 'CRITICAL'
                              ? 'bg-rose-100 text-rose-700'
                              : 'bg-amber-100 text-amber-700'
                          }`}
                        >
                          {evt.severity || 'WARNING'}
                        </span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="5" className="p-6 text-center text-slate-400">
                      No safety incidents recorded for this vehicle.
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
