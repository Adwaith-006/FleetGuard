import React from 'react';
import { X, Download, ShieldCheck, FileText, Printer } from 'lucide-react';
import { calculateSafetyScore } from '../utils/safetyScore';
import { downloadPDFReport } from '../utils/pdfGenerator';
import { formatDateTime } from '../utils/dateUtils';

export default function ReportPreviewModal({ isOpen, onClose, driver, vehicle, events, dateRange, sessionId }) {
  if (!isOpen || !driver) return null;

  const scoreInfo = calculateSafetyScore(events);
  const drowsinessCount = events.filter(e => e.event_type === 'DROWSINESS').length;
  const yawningCount = events.filter(e => e.event_type === 'YAWNING').length;
  const phoneCount = events.filter(e => e.event_type === 'PHONE_DETECTED' || e.event_type === 'PHONE_USAGE').length;
  const criticalCount = events.filter(e => e.severity === 'CRITICAL' || e.status === 'UNSAFE' || e.status === 'HIGH_RISK').length;

  const handleDownload = () => {
    downloadPDFReport({ driver, vehicle, events, dateRange, sessionId });
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto print:p-0 print:static print:bg-white">
      <div className="bg-white rounded-2xl max-w-4xl w-full shadow-2xl overflow-hidden my-8 border border-slate-200 print:shadow-none print:border-none print:my-0 print:max-w-none">
        
        {/* Modal Top Header (Hidden on Print) */}
        <div className="px-6 py-4 bg-slate-900 text-white flex items-center justify-between border-b border-slate-800 print:hidden">
          <div className="flex items-center gap-3">
            <FileText className="w-5 h-5 text-indigo-400" />
            <h2 className="font-bold text-lg">Driver Safety Report Preview</h2>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handlePrint}
              className="flex items-center gap-2 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg transition-colors"
            >
              <Printer className="w-4 h-4" />
              <span>Print</span>
            </button>

            <button
              onClick={handleDownload}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg transition-colors shadow-xs"
            >
              <Download className="w-4 h-4" />
              <span>Download PDF</span>
            </button>

            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Report Content Body */}
        <div className="p-8 max-h-[80vh] print:max-h-none overflow-y-auto print:overflow-visible space-y-6">
          
          {/* Document Header */}
          <div className="border-b border-slate-200 pb-6 flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 text-indigo-600 font-bold text-sm uppercase tracking-wider mb-1">
                <ShieldCheck className="w-4 h-4" />
                Vanguard Fleet Safety System
              </div>
              <h1 className="text-2xl font-black text-slate-900">DRIVER SAFETY PERFORMANCE REPORT</h1>
              <p className="text-xs text-slate-500 mt-1">Generated on {new Date().toLocaleDateString()}</p>
            </div>
            <div className="text-right">
              <span className={`inline-flex items-center px-4 py-1.5 rounded-full text-xs font-bold border ${scoreInfo.color}`}>
                {scoreInfo.status} (Score: {scoreInfo.score}/100)
              </span>
            </div>
          </div>

          {/* Profile & Vehicle Grid */}
          <div className="grid grid-cols-2 gap-4 bg-slate-50 p-4 rounded-xl border border-slate-200">
            <div>
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Driver Profile</h3>
              <p className="text-sm font-semibold text-slate-900">{driver.name}</p>
              <p className="text-xs text-slate-600">ID: {driver.id}</p>
              <p className="text-xs text-slate-600">License: {driver.license || 'N/A'}</p>
            </div>
            <div>
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Vehicle & Test Session</h3>
              <p className="text-sm font-semibold text-slate-900">{vehicle?.vehicleNo || 'Prototype Vehicle'}</p>
              <p className="text-xs text-slate-600">Model: {vehicle?.model || 'College Demo AI Test Rig'}</p>
              <p className="text-xs font-mono text-indigo-600 font-semibold mt-0.5">Session: {sessionId || 'All Sessions'}</p>
              <p className="text-xs text-slate-500">Period: {dateRange || 'All Time'}</p>
            </div>
          </div>

          {/* KPI Summary Grid */}
          <div className="grid grid-cols-5 gap-3">
            <div className="p-3 bg-slate-100 rounded-lg text-center">
              <p className="text-xs font-medium text-slate-500">Total Events</p>
              <p className="text-xl font-black text-slate-800 mt-1">{events.length}</p>
            </div>
            <div className="p-3 bg-indigo-50 rounded-lg text-center">
              <p className="text-xs font-medium text-indigo-700">Drowsiness</p>
              <p className="text-xl font-black text-indigo-900 mt-1">{drowsinessCount}</p>
            </div>
            <div className="p-3 bg-amber-50 rounded-lg text-center">
              <p className="text-xs font-medium text-amber-700">Yawning</p>
              <p className="text-xl font-black text-amber-900 mt-1">{yawningCount}</p>
            </div>
            <div className="p-3 bg-rose-50 rounded-lg text-center">
              <p className="text-xs font-medium text-rose-700">Phone Use</p>
              <p className="text-xl font-black text-rose-900 mt-1">{phoneCount}</p>
            </div>
            <div className="p-3 bg-purple-50 rounded-lg text-center">
              <p className="text-xs font-medium text-purple-700">Critical Alerts</p>
              <p className="text-xl font-black text-purple-900 mt-1">{criticalCount}</p>
            </div>
          </div>

          {/* Detailed Event Table */}
          <div>
            <h3 className="text-sm font-bold text-slate-800 mb-3">Event History Log</h3>
            <div className="overflow-x-auto border border-slate-200 rounded-xl">
              <table className="w-full text-left text-xs text-slate-700">
                <thead className="bg-slate-100 text-slate-600 font-semibold border-b border-slate-200">
                  <tr>
                    <th className="p-3">Date & Time</th>
                    <th className="p-3">Event Type</th>
                    <th className="p-3">Duration</th>
                    <th className="p-3">Objective Status</th>
                    <th className="p-3">Metrics</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {events.length > 0 ? (
                    events.map((evt, idx) => (
                      <tr key={evt.event_id || idx} className="hover:bg-slate-50">
                        <td className="p-3 font-medium">
                          {formatDateTime(evt.start_time || evt.timestamp)}
                        </td>
                        <td className="p-3 font-semibold">{evt.event_type}</td>
                        <td className="p-3">{evt.duration}s</td>
                        <td className="p-3">
                          <span
                            className={`px-2 py-0.5 rounded-md text-[11px] font-bold ${
                              evt.status === 'UNSAFE' || evt.status === 'HIGH_RISK' || evt.severity === 'CRITICAL'
                                ? 'bg-rose-100 text-rose-700'
                                : evt.status === 'ATTENTION_REQUIRED' || evt.severity === 'WARNING'
                                ? 'bg-amber-100 text-amber-700'
                                : 'bg-blue-100 text-blue-700'
                            }`}
                          >
                            {evt.status || evt.severity || 'OBSERVED'}
                          </span>
                        </td>
                        <td className="p-3 font-mono text-[11px] text-slate-500">
                          {evt.metrics?.avg_ear
                            ? `EAR: ${evt.metrics.avg_ear}`
                            : evt.metrics?.max_mar
                            ? `MAR: ${evt.metrics.max_mar}`
                            : evt.confidence
                            ? `Conf: ${evt.confidence}`
                            : '-'}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="5" className="p-4 text-center text-slate-400">
                        No events recorded for this selection.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Footer (Hidden on Print) */}
        <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex justify-end gap-3 print:hidden">
          <button
            onClick={onClose}
            className="px-4 py-2 border border-slate-300 text-slate-700 text-xs font-semibold rounded-lg hover:bg-slate-100"
          >
            Close
          </button>
          <button
            onClick={handleDownload}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-xs font-semibold rounded-lg hover:bg-indigo-700 shadow-xs"
          >
            <Download className="w-4 h-4" />
            <span>Download PDF</span>
          </button>
        </div>

      </div>
    </div>
  );
}
