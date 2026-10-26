import React, { useEffect, useState } from 'react';
import Header from '../components/Header';
import { MOCK_DRIVERS, MOCK_VEHICLES, fetchEvents } from '../services/dataService';
import ReportPreviewModal from '../components/ReportPreviewModal';
import { downloadPDFReport } from '../utils/pdfGenerator';
import { FileSpreadsheet, Download, Eye, Calendar, User, Truck, Radio } from 'lucide-react';

export default function Reports() {
  const [selectedDriverId, setSelectedDriverId] = useState('DRV001');
  const [selectedVehicleId, setSelectedVehicleId] = useState('VEH001');
  const [selectedSessionId, setSelectedSessionId] = useState('ALL');
  const [dateRange, setDateRange] = useState('All Time');
  const [allEvents, setAllEvents] = useState([]);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);

  useEffect(() => {
    fetchEvents().then(setAllEvents);
  }, []);

  const availableSessions = Array.from(new Set(allEvents.map(e => e.session_id).filter(Boolean)));

  const selectedDriver = MOCK_DRIVERS.find(d => d.id === selectedDriverId) || MOCK_DRIVERS[0];
  const selectedVehicle = MOCK_VEHICLES.find(v => v.id === selectedVehicleId) || MOCK_VEHICLES[0];

  const filteredEvents = allEvents.filter(e => {
    const matchDriver = !selectedDriver || e.driver_id === selectedDriver.id || e.driver_name === selectedDriver.name;
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
                {MOCK_DRIVERS.map(d => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
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
                {MOCK_VEHICLES.map(v => (
                  <option key={v.id} value={v.id}>{v.vehicleNo}</option>
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
            <span className="text-slate-500 font-medium">
              {filteredEvents.length === 0 ? "Clean demonstration slate (0 recorded incidents)" : "Ready for report export"}
            </span>
          </div>

          {/* Action Buttons */}
          <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-4">
            <button
              onClick={() => setIsPreviewOpen(true)}
              className="flex items-center gap-2 px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-xl transition-colors"
            >
              <Eye className="w-4 h-4" />
              <span>Preview Report</span>
            </button>

            <button
              onClick={handleDownload}
              className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-xl transition-all shadow-md shadow-indigo-600/20"
            >
              <Download className="w-4 h-4" />
              <span>Download PDF Report</span>
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
