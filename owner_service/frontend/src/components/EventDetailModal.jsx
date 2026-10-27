import React, { useState } from 'react';
import { X, Sparkles, AlertTriangle, ShieldCheck, Clock, User, Truck, Activity, RefreshCw } from 'lucide-react';
import { requestAiAnalysis } from '../services/dataService';

export default function EventDetailModal({ event, isOpen, onClose, onAnalysisUpdated }) {
  const [analyzing, setAnalyzing] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [currentAnalysis, setCurrentAnalysis] = useState(event?.ai_analysis || null);

  if (!isOpen || !event) return null;

  const analysis = currentAnalysis || event.ai_analysis;
  const metrics = event.metrics || {};

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setErrorMsg(null);
    try {
      const res = await requestAiAnalysis(event.event_id);
      if (res && res.status === 'success') {
        setCurrentAnalysis(res);
        if (onAnalysisUpdated) onAnalysisUpdated(event.event_id, res);
      } else if (res && res.summary) {
        setCurrentAnalysis(res);
      } else {
        setErrorMsg(res?.message || 'Failed to complete Gemma AI analysis.');
      }
    } catch (err) {
      setErrorMsg(`Error contacting analysis service: ${err.message}`);
    } finally {
      setAnalyzing(false);
    }
  };

  const getSeverityBadge = (sev) => {
    const s = (sev || 'WARNING').toUpperCase();
    if (s === 'CRITICAL') return 'bg-rose-100 text-rose-800 border-rose-300';
    if (s === 'HIGH' || s === 'WARNING') return 'bg-amber-100 text-amber-800 border-amber-300';
    return 'bg-emerald-100 text-emerald-800 border-emerald-300';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
      <div className="bg-white rounded-3xl max-w-2xl w-full border border-slate-200 shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
        
        {/* Modal Header */}
        <div className="p-6 bg-slate-900 text-white flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white shadow-md">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold">{event.event_type}</h3>
                <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${getSeverityBadge(event.severity)}`}>
                  {event.severity || 'WARNING'}
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono mt-0.5">ID: {event.event_id}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-6 overflow-y-auto flex-1">
          
          {/* Metadata Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Driver</span>
              <span className="font-semibold text-slate-800 truncate block mt-0.5">{event.driver_name || event.driver_id || 'DRV001'}</span>
            </div>
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Vehicle</span>
              <span className="font-semibold text-slate-800 truncate block mt-0.5">{event.vehicle_no || event.vehicle_id || 'VEH001'}</span>
            </div>
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Duration</span>
              <span className="font-bold text-slate-800 block mt-0.5">{event.duration}s</span>
            </div>
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Status</span>
              <span className="font-bold text-indigo-700 block mt-0.5">{event.status || 'OBSERVED'}</span>
            </div>
          </div>

          {/* Quantitative Metrics Details */}
          {Object.keys(metrics).length > 0 && (
            <div className="p-4 bg-slate-50/80 rounded-2xl border border-slate-200 space-y-2">
              <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block">Telemetry Metrics</span>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                {metrics.avg_ear !== undefined && (
                  <div>
                    <span className="text-slate-400 block">Avg EAR:</span>
                    <strong className="text-slate-800">{metrics.avg_ear}</strong>
                  </div>
                )}
                {metrics.min_ear !== undefined && (
                  <div>
                    <span className="text-slate-400 block">Min EAR:</span>
                    <strong className="text-slate-800">{metrics.min_ear}</strong>
                  </div>
                )}
                {metrics.roll !== undefined && (
                  <div>
                    <span className="text-slate-400 block">Head Roll:</span>
                    <strong className="text-slate-800">{metrics.roll}°</strong>
                  </div>
                )}
                {metrics.pitch !== undefined && (
                  <div>
                    <span className="text-slate-400 block">Head Pitch:</span>
                    <strong className="text-slate-800">{metrics.pitch}°</strong>
                  </div>
                )}
                {metrics.max_confidence !== undefined && (
                  <div>
                    <span className="text-slate-400 block">Phone Confidence:</span>
                    <strong className="text-slate-800">{(metrics.max_confidence * 100).toFixed(0)}%</strong>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Local Gemma AI Analysis Section */}
          <div className="p-5 bg-gradient-to-br from-indigo-50/80 via-white to-purple-50/50 rounded-2xl border border-indigo-100 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-indigo-600" />
                <h4 className="text-sm font-bold text-slate-900">Local Gemma AI Safety Analysis</h4>
              </div>
              <button
                onClick={handleAnalyze}
                disabled={analyzing}
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-all"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${analyzing ? 'animate-spin' : ''}`} />
                <span>{analyzing ? 'Analyzing with Gemma...' : (analysis ? 'Re-Analyze' : 'Analyze with Gemma')}</span>
              </button>
            </div>

            {errorMsg && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700">
                {errorMsg}
              </div>
            )}

            {analysis ? (
              <div className="space-y-3.5 text-xs">
                {/* Summary */}
                <div>
                  <span className="font-bold text-slate-500 uppercase text-[10px] block">Incident Summary</span>
                  <p className="text-slate-800 font-medium mt-0.5 leading-relaxed">{analysis.summary}</p>
                </div>

                {/* Risk Level & Recommendation */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="p-3 bg-white rounded-xl border border-slate-200">
                    <span className="font-bold text-slate-500 uppercase text-[10px] block">Assessed Risk Level</span>
                    <span className={`inline-block px-2.5 py-0.5 rounded-full font-bold text-[11px] mt-1 border ${getSeverityBadge(analysis.risk_level)}`}>
                      {analysis.risk_level || 'EVALUATED'}
                    </span>
                  </div>
                  <div className="p-3 bg-white rounded-xl border border-slate-200">
                    <span className="font-bold text-slate-500 uppercase text-[10px] block">Analysis Source</span>
                    <span className="text-slate-800 font-semibold block mt-1">AI Safety Intelligence</span>
                  </div>
                </div>

                {/* Supporting Evidence */}
                {analysis.supporting_evidence && analysis.supporting_evidence.length > 0 && (
                  <div>
                    <span className="font-bold text-slate-500 uppercase text-[10px] block mb-1">Supporting Telemetry Evidence</span>
                    <ul className="list-disc pl-4 space-y-0.5 text-slate-700">
                      {analysis.supporting_evidence.map((ev, i) => (
                        <li key={i}>{ev}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Recommended Follow-up */}
                {analysis.recommended_action && (
                  <div className="p-3.5 bg-indigo-50 border border-indigo-200 rounded-xl">
                    <span className="font-bold text-indigo-900 uppercase text-[10px] block">Recommended Fleet Follow-up</span>
                    <p className="text-indigo-950 font-medium mt-0.5">{analysis.recommended_action}</p>
                  </div>
                )}

                <p className="text-[10px] text-slate-400 italic">
                  Advisory safety insight based on verified vehicle telemetry. Not a medical evaluation or replacement for vehicle safety procedures.
                </p>
              </div>
            ) : (
              <div className="text-center py-6 text-slate-400 text-xs">
                <Sparkles className="w-8 h-8 text-indigo-300 mx-auto mb-2" />
                <p className="font-medium text-slate-600">No safety analysis requested yet for this event.</p>
                <p className="text-[11px] mt-1">Click the button above to generate a structured risk assessment.</p>
              </div>
            )}
          </div>

        </div>

        {/* Modal Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 rounded-xl text-xs font-semibold transition-colors"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
}
