import React, { useEffect, useState } from 'react';
import Header from '../components/Header';
import { fetchEvents } from '../services/dataService';
import { useWebSocket } from '../context/WebSocketContext';
import { Search, Filter } from 'lucide-react';

export default function SafetyHistory() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const { liveEventsList } = useWebSocket();

  useEffect(() => {
    fetchEvents().then(data => {
      setEvents(data);
      setLoading(false);
    });
  }, []);

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

  const filteredEvents = allCurrentEvents.filter(evt => {
    const matchesType = typeFilter === 'ALL' || evt.event_type === typeFilter;
    const currentStatus = evt.status || evt.severity || 'OBSERVED';
    const matchesStatus = statusFilter === 'ALL' || currentStatus === statusFilter;
    
    const query = searchQuery.toLowerCase();
    const matchesSearch =
      !query ||
      (evt.driver_name && evt.driver_name.toLowerCase().includes(query)) ||
      (evt.vehicle_no && evt.vehicle_no.toLowerCase().includes(query)) ||
      (evt.event_type && evt.event_type.toLowerCase().includes(query)) ||
      (evt.event_id && evt.event_id.toLowerCase().includes(query));

    return matchesType && matchesStatus && matchesSearch;
  });

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

  return (
    <div className="flex-1 bg-slate-50 min-h-screen">
      <Header title="Safety History Log" subtitle="Real-time objective event records from Python webcam AI" />

      <main className="p-8 max-w-7xl mx-auto space-y-6">
        
        {/* Filter Controls Bar */}
        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-1 min-w-[240px]">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
              <input
                type="text"
                placeholder="Search Event ID, driver, vehicle..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-500">Event Type:</span>
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="ALL">All Types</option>
                <option value="DROWSINESS">Drowsiness</option>
                <option value="YAWNING">Yawning</option>
                <option value="PHONE_DETECTED">Phone Detected</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-500">Objective Status:</span>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="ALL">All Statuses</option>
                <option value="BRIEF">BRIEF</option>
                <option value="ATTENTION_REQUIRED">ATTENTION_REQUIRED</option>
                <option value="UNSAFE">UNSAFE</option>
                <option value="OBSERVED">OBSERVED</option>
                <option value="DROWSINESS_DETECTED">DROWSINESS_DETECTED</option>
                <option value="HIGH_RISK">HIGH_RISK</option>
              </select>
            </div>
          </div>
        </div>

        {/* History Log Table */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="p-6 border-b border-slate-200 flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-slate-800">Event History Log ({filteredEvents.length})</h2>
              <p className="text-xs text-slate-500">Objective camera AI events broadcast via WebSocket</p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                <tr>
                  <th className="p-4">Event ID</th>
                  <th className="p-4">Date & Time</th>
                  <th className="p-4">Event Type</th>
                  <th className="p-4">Driver</th>
                  <th className="p-4">Vehicle</th>
                  <th className="p-4">Duration</th>
                  <th className="p-4">Objective Status</th>
                  <th className="p-4">Metrics</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading ? (
                  <tr>
                    <td colSpan="8" className="p-6 text-center text-slate-400">Loading events...</td>
                  </tr>
                ) : filteredEvents.length > 0 ? (
                  filteredEvents.map((evt, idx) => (
                    <tr key={evt.event_id || idx} className="hover:bg-slate-50">
                      <td className="p-4 font-mono text-[11px] text-indigo-600 font-semibold">{evt.event_id || `EVT-${idx}`}</td>
                      <td className="p-4 font-medium text-slate-900">
                        {evt.start_time ? new Date(evt.start_time).toLocaleString() : 'N/A'}
                      </td>
                      <td className="p-4 font-bold text-slate-800">{evt.event_type}</td>
                      <td className="p-4 font-semibold text-slate-800">{evt.driver_name || 'Prototype Driver (Demo Test)'}</td>
                      <td className="p-4 text-slate-600">{evt.vehicle_no || 'Prototype Vehicle (Cabin Rig)'}</td>
                      <td className="p-4 font-semibold">{evt.duration}s</td>
                      <td className="p-4">
                        <span className={`px-2.5 py-1 rounded-md text-[11px] font-bold border ${getStatusBadgeStyle(evt.status || evt.severity)}`}>
                          {evt.status || evt.severity || 'OBSERVED'}
                        </span>
                      </td>
                      <td className="p-4 font-mono text-slate-500">
                        {evt.metrics?.avg_ear
                          ? `avg_ear: ${evt.metrics.avg_ear}`
                          : evt.metrics?.max_mar
                          ? `max_mar: ${evt.metrics.max_mar}`
                          : evt.metrics?.max_confidence
                          ? `confidence: ${evt.metrics.max_confidence}`
                          : evt.confidence
                          ? `confidence: ${evt.confidence}`
                          : '-'}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="8" className="p-8 text-center text-slate-400">
                      No safety events recorded yet. Live camera AI monitoring will stream genuine events here.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

      </main>
    </div>
  );
}
