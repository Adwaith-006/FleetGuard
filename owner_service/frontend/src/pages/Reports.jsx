import React, { useEffect, useState } from 'react';
import Header from '../components/Header';
import { fetchDrivers, fetchVehicles, fetchEvents } from '../services/dataService';
import ReportPreviewModal from '../components/ReportPreviewModal';
import { downloadPDFReport } from '../utils/pdfGenerator';
import { FileSpreadsheet, Download, Eye, Calendar, User, Truck, Radio } from 'lucide-react';

export default function Reports() {
  const [drivers, setDrivers] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [selectedDriverId, setSelectedDriverId] = useState('DRV001');
  const [selectedVehicleId, setSelectedVehicleId] = useState('VEH001');
  const [selectedSessionId, setSelectedSessionId] = useState('ALL');
  const [dateRange, setDateRange] = useState('All Time');
  const [allEvents, setAllEvents] = useState([]);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [driversData, vehiclesData, eventsData] = await Promise.all([
          fetchDrivers(),
          fetchVehicles(),
          fetchEvents()
        ]);
        setDrivers(driversData || []);
        setVehicles(vehiclesData || []);
        setAllEvents(eventsData || []);

        if (driversData && driversData.length > 0) {
          setSelectedDriverId(driversData[0].driver_id || driversData[0].id);
        }
        if (vehiclesData && vehiclesData.length > 0) {
          setSelectedVehicleId(vehiclesData[0].id);
        }
      } catch (err) {
        console.warn("Failed to load report parameters:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const availableSessions = Array.from(new Set(allEvents.map(e => e.session_id).filter(Boolean)));

  const selectedDriver = drivers.find(d => (d.driver_id || d.id) === selectedDriverId) || drivers[0] || {
    id: selectedDriverId,
    name: 'Prototype Driver'
  };
  const selectedVehicle = vehicles.find(v => v.id === selectedVehicleId) || vehicles[0] || {
    id: selectedVehicleId,
    vehicleNo: 'Cabin Rig'
  };

  const filteredEvents = allEvents.filter(e => {
    const driverId = selectedDriver.driver_id || selectedDriver.id;
    const matchDriver = !selectedDriver || e.driver_id === driverId || e.driver_name === selectedDriver.driver_name;
    const matchVehicle = !selectedVehicle || e.vehicle_id === selectedVehicle.id || e.vehicle_no === selectedVehicle.vehicleNo;
    const matchSession = selectedSessionId === 'ALL' || e.session_id === selectedSessionId;
    return matchDriver && matchVehicle && matchSession;
  });

  const handleDownload = () => {
    downloadPDFReport({
      driver: selectedDriver,
      vehicle: selectedVehicle,
      events: filteredEvents,
      dateRange,
      sessionId: selectedSessionId !== 'ALL' ? selectedSessionId : 'All Recorded Sessions'
    });
  };

  return (
    <div className="flex-1 bg-slate-50 min-h-screen">
      <Header title="Safety Reports & PDF Export" subtitle="Generate verifiable Driver Safety Performance Reports from live telemetry" />

      <main className="p-8 max-w-5xl mx-auto space-y-8">
        
        {/* Report Configurator Card */}
        <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-xs space-y-6">
          
          <div className="flex items-center gap-3 border-b border-slate-100 pb-5">
            <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600">
              <FileSpreadsheet className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">Generate Driver Safety Report</h2>
              <p className="text-xs text-slate-500">Configure parameters for evaluation and PDF download based strictly on actual events</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
            
            {/* Driver Select */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-2 flex items-center gap-1.5">
                <User className="w-4 h-4 text-indigo-600" />
                <span>Driver Profile</span>
              </label>
              <select
                value={selectedDriverId}
                onChange={(e) => setSelectedDriverId(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-xs font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {drivers.map(d => {
                  const dId = d.driver_id || d.id;
                  const dName = d.driver_name || d.name || 'Prototype Driver';
                  return (
                    <option key={dId} value={dId}>{dName} ({dId})</option>
                  );
                })}
              </select>
            </div>

            {/* Vehicle Select */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-2 flex items-center gap-1.5">
                <Truck className="w-4 h-4 text-blue-600" />
                <span>Vehicle Rig</span>
              </label>
              <select
                value={selectedVehicleId}
                onChange={(e) => setSelectedVehicleId(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-xs font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {vehicles.map(v => (
                  <option key={v.id} value={v.id}>{v.vehicleNo} ({v.id})</option>
                ))}
              </select>
            </div>

            {/* Test Session Select */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-2 flex items-center gap-1.5">
                <Radio className="w-4 h-4 text-emerald-600" />
                <span>Test Session</span>
              </label>
              <select
                value={selectedSessionId}
                onChange={(e) => setSelectedSessionId(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-xs font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="ALL">All Test Sessions ({availableSessions.length})</option>
                {availableSessions.map((sess, idx) => (
                  <option key={sess} value={sess}>
                    {idx === 0 ? `Latest: ${sess}` : sess}
                  </option>
                ))}
              </select>
            </div>

            {/* Date Range Select */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-2 flex items-center gap-1.5">
                <Calendar className="w-4 h-4 text-amber-600" />
                <span>Reporting Period</span>
              </label>
              <select
                value={dateRange}
                onChange={(e) => setDateRange(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-xs font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="All Time">All Time</option>
                <option value="Current Session">Current Demonstration</option>
                <option value="Last 7 Days">Last 7 Days</option>
              </select>
            </div>

          </div>

          {/* Filter Status Badge */}
          <div className="bg-slate-50 rounded-xl p-3 border border-slate-200 flex items-center justify-between text-xs">
            <span className="text-slate-600">
              Matching Safety Events: <strong className="text-slate-900">{filteredEvents.length}</strong>
            </span>
            <span className="text-slate-400 font-medium">
              Report anchored to actual safety telemetry
            </span>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-4 pt-2">
            <button
              onClick={() => setIsPreviewOpen(true)}
              className="flex items-center gap-2 px-5 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-indigo-600/20"
            >
              <Eye className="w-4 h-4" />
              <span>Preview Report</span>
            </button>

            <button
              onClick={handleDownload}
              className="flex items-center gap-2 px-5 py-3 bg-slate-800 hover:bg-slate-900 text-white rounded-xl text-xs font-bold transition-all"
            >
              <Download className="w-4 h-4" />
              <span>Direct PDF Download</span>
            </button>
          </div>

        </div>

      </main>

      <ReportPreviewModal
        isOpen={isPreviewOpen}
        onClose={() => setIsPreviewOpen(false)}
        driver={selectedDriver}
        vehicle={selectedVehicle}
        events={filteredEvents}
        dateRange={dateRange}
        sessionId={selectedSessionId !== 'ALL' ? selectedSessionId : 'All Recorded Sessions'}
      />
    </div>
  );
}
