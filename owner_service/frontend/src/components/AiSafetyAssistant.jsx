import React, { useState, useEffect, useRef } from 'react';
import {
  Sparkles,
  Send,
  Clock,
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
  Bot,
  User,
  History,
  FileText,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Info,
  Check,
  CheckCheck,
  Shield,
  HelpCircle,
  Copy,
  ExternalLink,
  RotateCcw,
  Smartphone,
  Eye,
  AlertCircle
} from 'lucide-react';
import { askSafetyQuestion, generateSafetySummary, fetchAiAnalyses } from '../services/dataService';
import EventDetailModal from './EventDetailModal';
import { formatDateTime } from '../utils/dateUtils';

const PRESET_QUESTIONS = [
  "What happened in the last 30 minutes?",
  "Why is this driver's safety rating low?",
  "Compare today with yesterday.",
  "Which events require the owner's attention?",
  "Give me recommendations based on the recorded events.",
  "Generate a detailed driving safety evaluation report."
];

const TIME_RANGES = [
  { id: '30m', label: 'Last 30 Min' },
  { id: '1h', label: 'Last 1 Hour' },
  { id: 'today', label: 'Today (24h)' },
  { id: 'yesterday', label: 'Yesterday' },
  { id: '7d', label: 'Last 7 Days' },
  { id: 'all', label: 'All History' }
];

/**
 * Lightweight, safe Markdown text renderer for assistant chat responses.
 * Parses headings, bullet lists, numbered lists, bold text, and inline code without innerHTML.
 */
function MarkdownContent({ text }) {
  if (!text) return null;

  const blocks = text.split(/\n\s*\n/);

  const formatInline = (str) => {
    if (!str) return '';
    const parts = [];
    const regex = /(\*\*.*?\*\*|`.*?`)/g;
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(str)) !== null) {
      if (match.index > lastIndex) {
        parts.push(str.substring(lastIndex, match.index));
      }
      const token = match[0];
      if (token.startsWith('**') && token.endsWith('**')) {
        parts.push(
          <strong key={match.index} className="font-bold text-slate-900">
            {token.slice(2, -2)}
          </strong>
        );
      } else if (token.startsWith('`') && token.endsWith('`')) {
        parts.push(
          <code key={match.index} className="px-1.5 py-0.5 rounded bg-slate-100 text-indigo-700 font-mono text-[11px] border border-slate-200">
            {token.slice(1, -1)}
          </code>
        );
      }
      lastIndex = match.index + token.length;
    }
    if (lastIndex < str.length) {
      parts.push(str.substring(lastIndex));
    }
    return parts.length > 0 ? parts : str;
  };

  return (
    <div className="space-y-2 text-xs text-slate-800 leading-relaxed">
      {blocks.map((block, idx) => {
        const trimmed = block.trim();
        if (!trimmed) return null;

        if (trimmed.startsWith('### ')) {
          return (
            <h4 key={idx} className="text-sm font-bold text-slate-900 mt-2 mb-1">
              {formatInline(trimmed.replace(/^###\s+/, ''))}
            </h4>
          );
        }
        if (trimmed.startsWith('## ')) {
          return (
            <h3 key={idx} className="text-sm font-extrabold text-slate-900 mt-2 mb-1">
              {formatInline(trimmed.replace(/^##\s+/, ''))}
            </h3>
          );
        }

        // Bullet lists
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          const lines = trimmed.split('\n').filter(l => l.trim().startsWith('- ') || l.trim().startsWith('* '));
          return (
            <ul key={idx} className="space-y-1 my-1.5 pl-2">
              {lines.map((line, i) => (
                <li key={i} className="flex items-start gap-2 text-slate-700">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 shrink-0 mt-1.5" />
                  <span>{formatInline(line.replace(/^[-*]\s+/, ''))}</span>
                </li>
              ))}
            </ul>
          );
        }

        // Numbered lists
        if (/^\d+\.\s+/.test(trimmed)) {
          const lines = trimmed.split('\n').filter(l => /^\d+\.\s+/.test(l.trim()));
          return (
            <ol key={idx} className="space-y-1 my-1.5 pl-2 list-decimal list-inside text-slate-700">
              {lines.map((line, i) => (
                <li key={i}>
                  <span>{formatInline(line.replace(/^\d+\.\s+/, ''))}</span>
                </li>
              ))}
            </ol>
          );
        }

        // Standard paragraph
        return (
          <p key={idx} className="leading-relaxed">
            {formatInline(trimmed)}
          </p>
        );
      })}
    </div>
  );
}

export default function AiSafetyAssistant({ driverId, driverName, vehicleNo, safetyScore, totalEvents, events = [] }) {
  const [question, setQuestion] = useState('');
  const [selectedRange, setSelectedRange] = useState('30m');
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const [savedAnalyses, setSavedAnalyses] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [copiedId, setCopiedId] = useState(null);
  const [expandedTelemetry, setExpandedTelemetry] = useState({});
  const [modalEvent, setModalEvent] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const chatBottomRef = useRef(null);
  const safeEvents = Array.isArray(events) ? events : [];

  const loadSavedAnalyses = async () => {
    if (!driverId) return;
    setHistoryLoading(true);
    try {
      const data = await fetchAiAnalyses(20, null, driverId);
      if (Array.isArray(data)) {
        setSavedAnalyses(data);
      }
    } catch (err) {
      console.warn('Could not load saved analyses:', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  // Initialize or reset conversation when driverId changes
  useEffect(() => {
    setMessages([
      {
        id: 'welcome',
        sender: 'ai',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: `Hi! I can help you monitor safety events, review driver scores, investigate drowsiness or distraction incidents, and explain performance trends for ${driverName || driverId || 'this driver'}. What would you like to check?`,
        isWelcome: true
      }
    ]);
    loadSavedAnalyses();
  }, [driverId, driverName]);

  // Scroll to bottom when messages update
  useEffect(() => {
    if (chatBottomRef.current) {
      chatBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading]);

  const handleCopy = (msgId, text) => {
    if (navigator?.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedId(msgId);
      setTimeout(() => setCopiedId(null), 2000);
    }
  };

  const toggleTelemetry = (msgId) => {
    setExpandedTelemetry(prev => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  const openIncidentModal = (evt) => {
    let fullEvt = evt;
    if (typeof evt === 'string') {
      fullEvt = safeEvents.find(e => e.event_id === evt) || {
        event_id: evt,
        event_type: 'SAFETY EVENT',
        severity: 'WARNING',
        timestamp: new Date().toISOString()
      };
    } else if (evt && !evt.start_time && !evt.timestamp) {
      const found = safeEvents.find(e => e.event_id === evt.event_id);
      if (found) fullEvt = { ...found, ...evt };
    }
    setModalEvent(fullEvt);
    setIsModalOpen(true);
  };

  const handleAsk = async (queryText = null) => {
    const q = (queryText || question).trim();
    if (!q || isLoading) return;

    const userMessageId = `user_${Date.now()}`;
    const newMessages = [
      ...messages,
      {
        id: userMessageId,
        sender: 'user',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: q,
        timeRange: selectedRange
      }
    ];

    setMessages(newMessages);
    setQuestion('');
    setIsLoading(true);

    try {
      // Build conversation history for natural follow-up context
      const convHistory = newMessages
        .filter(m => !m.isWelcome && m.text)
        .slice(-5)
        .map(m => ({
          role: m.sender === 'user' ? 'user' : 'assistant',
          content: m.text
        }));

      const res = await askSafetyQuestion(driverId, q, selectedRange, convHistory);

      // Sync active range if the query updated the effective window
      if (res.time_range && res.time_range !== selectedRange) {
        setSelectedRange(res.time_range);
      }

      const aiMessage = {
        id: `ai_${Date.now()}`,
        sender: 'ai',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: res.answer || res.summary || 'Answer generated.',
        data: res,
        queryText: q,
        isError: res.status === 'error'
      };

      setMessages(prev => [...prev, aiMessage]);
      loadSavedAnalyses();
    } catch (err) {
      console.error('AI assistant query error:', err);
      setMessages(prev => [
        ...prev,
        {
          id: `ai_err_${Date.now()}`,
          sender: 'ai',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          text: "I couldn't complete that request just now. Please try again.",
          queryText: q,
          isError: true
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickSummary = async () => {
    if (isLoading) return;
    const summaryPrompt = `Generate a detailed driving safety evaluation report for '${selectedRange}'.`;
    handleAsk(summaryPrompt);
  };

  const getRiskBadge = (level = 'SAFE') => {
    const l = (level || 'SAFE').toUpperCase();
    if (l === 'CRITICAL') return 'bg-rose-500/10 text-rose-600 border-rose-300';
    if (l === 'HIGH' || l === 'HIGH RISK') return 'bg-rose-50 text-rose-700 border-rose-200';
    if (l === 'MEDIUM' || l === 'WARNING') return 'bg-amber-50 text-amber-700 border-amber-200';
    return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  };

  return (
    <div className="bg-white rounded-2xl border border-indigo-100 shadow-xs overflow-hidden flex flex-col">
      {/* Header bar */}
      <div className="bg-gradient-to-r from-indigo-900 via-indigo-800 to-slate-900 text-white p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/30 border border-indigo-400/30 flex items-center justify-center text-indigo-300 shadow-inner">
              <Sparkles className="w-5 h-5 text-indigo-200 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-white tracking-wide">AI Safety Assistant</h3>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/30 text-indigo-200 border border-indigo-400/30">
                  Fleet Intelligence
                </span>
              </div>
              <p className="text-xs text-indigo-200/80 mt-0.5">
                Conversational fleet intelligence grounded in verified safety telemetry for Driver {driverId}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-950/60 hover:bg-indigo-950 text-indigo-200 text-xs font-semibold border border-indigo-800/80 transition-all cursor-pointer"
              title="View saved safety evaluations"
            >
              <History className="w-3.5 h-3.5" />
              <span>Saved Evaluations ({savedAnalyses.length})</span>
              {showHistory ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>

            <button
              onClick={handleQuickSummary}
              disabled={isLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold shadow-md shadow-indigo-600/30 transition-all cursor-pointer"
              title="Generate a structured driving safety evaluation report"
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Formal Report</span>
            </button>
          </div>
        </div>

        {/* Time range selector pills */}
        <div className="mt-4 pt-4 border-t border-indigo-800/60 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-indigo-300/80 font-medium flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" /> Time Range:
            </span>
            <div className="inline-flex rounded-lg bg-indigo-950/70 p-1 border border-indigo-800/60 gap-1">
              {TIME_RANGES.map(tr => (
                <button
                  key={tr.id}
                  onClick={() => setSelectedRange(tr.id)}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
                    selectedRange === tr.id
                      ? 'bg-indigo-600 text-white shadow-xs font-bold'
                      : 'text-indigo-200 hover:text-white'
                  }`}
                >
                  {tr.label}
                </button>
              ))}
            </div>
          </div>

          <div className="text-[11px] text-indigo-300/80 flex items-center gap-2">
            <span>Verified Events: <strong className="text-white">{safeEvents.length}</strong></span>
            <span>•</span>
            <span>Official Rating: <strong className="text-white">{(safetyScore !== undefined && safetyScore !== null) ? safetyScore : 100}/100</strong></span>
          </div>
        </div>
      </div>

      {/* Saved analyses drawer */}
      {showHistory && (
        <div className="bg-slate-50 border-b border-slate-200 p-5 space-y-3 transition-all">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <History className="w-4 h-4 text-indigo-600" />
              <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                Saved Safety Evaluations
              </h4>
            </div>
            <button
              onClick={loadSavedAnalyses}
              className="text-xs text-indigo-600 hover:text-indigo-800 font-medium flex items-center gap-1 cursor-pointer"
            >
              <RefreshCw className={`w-3 h-3 ${historyLoading ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
          </div>

          {savedAnalyses.length === 0 ? (
            <p className="text-xs text-slate-400 italic">No previous AI analyses stored for driver {driverId} yet.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-56 overflow-y-auto pr-1">
              {savedAnalyses.map((ana, idx) => (
                <div
                  key={ana.analysis_id || idx}
                  className="bg-white p-3.5 rounded-xl border border-slate-200 hover:border-indigo-300 transition-all text-xs shadow-2xs space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-900 truncate max-w-[220px]">
                      {ana.question || 'Safety Evaluation'}
                    </span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${getRiskBadge(ana.risk_level)}`}>
                      {ana.risk_level || 'ANALYZED'}
                    </span>
                  </div>
                  <p className="text-slate-600 line-clamp-2 text-[11px]">
                    {ana.summary || ana.answer}
                  </p>
                  <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-100">
                    <span className="font-medium text-slate-500">{ana.analysis_type ? ana.analysis_type.replace('_', ' ') : 'Evaluation'}</span>
                    <span>{formatDateTime(ana.created_at)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Conversation Thread */}
      <div className="p-6 space-y-4 max-h-[520px] overflow-y-auto bg-slate-50/50">
        {messages.map(msg => {
          const isFormal = msg.data?.is_formal_report === true;
          const isGreeting = msg.data?.intent === 'GREETING_OR_SOCIAL' || (!msg.data?.telemetry_facts && !msg.data?.is_formal_report) || msg.isWelcome;
          const showTele = expandedTelemetry[msg.id];
          const relevantEvents = msg.data?.relevant_events || [];

          return (
            <div
              key={msg.id}
              className={`flex gap-3 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.sender === 'ai' && (
                <div className="w-8 h-8 rounded-xl bg-indigo-600 text-white flex items-center justify-center shrink-0 shadow-sm shadow-indigo-600/30">
                  <Bot className="w-4 h-4" />
                </div>
              )}

              <div className={`max-w-[85%] rounded-2xl p-4 text-xs space-y-3 ${
                msg.sender === 'user'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                  : 'bg-white border border-slate-200 shadow-2xs text-slate-800'
              }`}>
                {/* User Message */}
                {msg.sender === 'user' ? (
                  <div>
                    <div className="flex items-center justify-between gap-3 text-[10px] text-indigo-200 mb-1">
                      <span className="font-bold uppercase tracking-wider">Fleet Owner</span>
                      <span>Range: {msg.timeRange || selectedRange} • {msg.timestamp}</span>
                    </div>
                    <p className="text-sm font-medium leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                  </div>
                ) : (
                  /* Assistant Message */
                  <div className="space-y-3">
                    {/* Header bar inside assistant card */}
                    <div className="flex items-center justify-between flex-wrap gap-2 pb-2 border-b border-slate-100">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-indigo-900 text-xs">AI Safety Assistant</span>
                      </div>

                      <div className="flex items-center gap-2">
                        {!isGreeting && msg.data?.risk_level && (
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${getRiskBadge(msg.data.risk_level)}`}>
                            {msg.data.risk_level}
                          </span>
                        )}

                        {/* Copy answer action */}
                        {msg.text && (
                          <button
                            onClick={() => handleCopy(msg.id, msg.text)}
                            className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-all cursor-pointer"
                            title="Copy answer to clipboard"
                          >
                            {copiedId === msg.id ? (
                              <CheckCheck className="w-3.5 h-3.5 text-emerald-600" />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )}
                          </button>
                        )}

                        <span className="text-[10px] text-slate-400">{msg.timestamp}</span>
                      </div>
                    </div>

                    {/* Error display with retry */}
                    {msg.isError && (
                      <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 space-y-2">
                        <p className="text-xs font-semibold">{msg.text}</p>
                        {msg.queryText && (
                          <button
                            onClick={() => handleAsk(msg.queryText)}
                            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-rose-600 text-white text-[11px] font-bold hover:bg-rose-700 transition-all cursor-pointer"
                          >
                            <RotateCcw className="w-3 h-3" /> Retry Question
                          </button>
                        )}
                      </div>
                    )}

                    {/* FORMAL REPORT VIEW: ONLY rendered if user explicitly asked for a formal report */}
                    {isFormal && !msg.isError && (
                      <div className="space-y-3">
                        {/* Executive Summary */}
                        {msg.data?.executive_summary && (
                          <div className="p-3 rounded-xl bg-indigo-50/70 border border-indigo-100/80">
                            <p className="text-xs font-bold text-indigo-950 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                              <Sparkles className="w-3.5 h-3.5 text-indigo-600" /> Executive Summary
                            </p>
                            <p className="text-xs text-indigo-900 font-medium leading-relaxed">
                              {msg.data.executive_summary}
                            </p>
                          </div>
                        )}

                        {/* Verified Telemetry Facts Bar for formal report */}
                        {msg.data?.telemetry_facts && (
                          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 space-y-2">
                            <div className="flex items-center justify-between text-[11px] font-bold text-slate-700">
                              <span className="flex items-center gap-1.5">
                                <Shield className="w-3.5 h-3.5 text-indigo-600" /> Telemetry Facts ({msg.data.telemetry_facts.time_range})
                              </span>
                              <span className="text-indigo-600 font-mono">
                                Official Score: {msg.data.telemetry_facts.safety_score}/100 ({msg.data.telemetry_facts.rating_status})
                              </span>
                            </div>

                            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-center text-[10px]">
                              <div className="bg-white p-2 rounded-lg border border-slate-200">
                                <span className="text-slate-400 block font-semibold">Total</span>
                                <span className="font-bold text-slate-800 text-xs">{msg.data.telemetry_facts.total_events}</span>
                              </div>
                              <div className="bg-white p-2 rounded-lg border border-slate-200">
                                <span className="text-indigo-600 block font-semibold">Drowsiness</span>
                                <span className="font-bold text-indigo-900 text-xs">{msg.data.telemetry_facts.drowsiness_count}</span>
                              </div>
                              <div className="bg-white p-2 rounded-lg border border-slate-200">
                                <span className="text-amber-600 block font-semibold">Yawning</span>
                                <span className="font-bold text-amber-900 text-xs">{msg.data.telemetry_facts.yawning_count}</span>
                              </div>
                              <div className="bg-white p-2 rounded-lg border border-slate-200">
                                <span className="text-rose-600 block font-semibold">Phone</span>
                                <span className="font-bold text-rose-900 text-xs">{msg.data.telemetry_facts.phone_count}</span>
                              </div>
                              <div className="bg-white p-2 rounded-lg border border-slate-200">
                                <span className="text-purple-600 block font-semibold">Critical</span>
                                <span className="font-bold text-purple-900 text-xs">{msg.data.telemetry_facts.critical_count}</span>
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Actionable Recommendations for formal report */}
                        {Array.isArray(msg.data?.recommendations) && msg.data.recommendations.length > 0 && (
                          <div className="p-3 rounded-xl bg-emerald-50/70 border border-emerald-200/80 space-y-1.5">
                            <p className="text-[11px] font-bold text-emerald-900 uppercase tracking-wider flex items-center gap-1.5">
                              <ShieldAlert className="w-3.5 h-3.5 text-emerald-700" /> Actionable Recommendations
                            </p>
                            <ul className="space-y-1">
                              {msg.data.recommendations.map((rec, i) => (
                                <li key={i} className="text-xs text-emerald-800 flex items-start gap-2 font-medium">
                                  <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                                  <span>{rec}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}

                    {/* NATURAL CONVERSATIONAL BODY */}
                    {!msg.isError && (
                      <div className="pt-1 text-slate-800 leading-relaxed">
                        <MarkdownContent text={msg.text} />
                      </div>
                    )}

                    {/* CLICKABLE INCIDENT EVIDENCE CHIPS: Show only if relevant events are tied to this answer */}
                    {!isGreeting && relevantEvents.length > 0 && (
                      <div className="pt-2 border-t border-slate-100 space-y-1.5">
                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1">
                          <ExternalLink className="w-3 h-3 text-indigo-500" /> Recorded Safety Incidents ({relevantEvents.length}):
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {relevantEvents.map((evt, idx) => (
                            <button
                              key={evt.event_id || idx}
                              onClick={() => openIncidentModal(evt)}
                              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-indigo-50 hover:border-indigo-200 border border-slate-200 text-[11px] font-medium text-slate-700 hover:text-indigo-700 transition-all cursor-pointer"
                              title="Click to view detailed incident telemetry"
                            >
                              <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                              <span className="font-bold">{evt.event_type}</span>
                              {evt.duration ? <span className="text-slate-400">({evt.duration}s)</span> : null}
                              <ExternalLink className="w-2.5 h-2.5 text-slate-400 ml-0.5" />
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* OPTIONAL COLLAPSIBLE TELEMETRY FOR ORDINARY QUERIES */}
                    {!isGreeting && !isFormal && msg.data?.telemetry_facts && !msg.isWelcome && (
                      <div className="pt-1">
                        <button
                          onClick={() => toggleTelemetry(msg.id)}
                          className="text-[10px] font-semibold text-slate-400 hover:text-indigo-600 flex items-center gap-1 transition-colors cursor-pointer"
                        >
                          <span>{showTele ? 'Hide' : 'Show'} Grounded Telemetry Baseline ({msg.data.telemetry_facts.time_range})</span>
                          {showTele ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        </button>

                        {showTele && (
                          <div className="mt-2 p-2.5 rounded-xl bg-slate-50 border border-slate-200 grid grid-cols-2 sm:grid-cols-5 gap-2 text-center text-[10px]">
                            <div className="bg-white p-1.5 rounded border border-slate-200">
                              <span className="text-slate-400 block font-semibold">Total</span>
                              <span className="font-bold text-slate-800 text-xs">{msg.data.telemetry_facts.total_events}</span>
                            </div>
                            <div className="bg-white p-1.5 rounded border border-slate-200">
                              <span className="text-indigo-600 block font-semibold">Drowsiness</span>
                              <span className="font-bold text-indigo-900 text-xs">{msg.data.telemetry_facts.drowsiness_count}</span>
                            </div>
                            <div className="bg-white p-1.5 rounded border border-slate-200">
                              <span className="text-amber-600 block font-semibold">Yawning</span>
                              <span className="font-bold text-amber-900 text-xs">{msg.data.telemetry_facts.yawning_count}</span>
                            </div>
                            <div className="bg-white p-1.5 rounded border border-slate-200">
                              <span className="text-rose-600 block font-semibold">Phone</span>
                              <span className="font-bold text-rose-900 text-xs">{msg.data.telemetry_facts.phone_count}</span>
                            </div>
                            <div className="bg-white p-1.5 rounded border border-slate-200">
                              <span className="text-purple-600 block font-semibold">Rating</span>
                              <span className="font-bold text-purple-900 text-xs">{msg.data.telemetry_facts.safety_score}/100</span>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* DYNAMIC SUGGESTED FOLLOW-UP QUERIES */}
                    {Array.isArray(msg.data?.suggested_followups) && msg.data.suggested_followups.length > 0 && (
                      <div className="pt-2 border-t border-slate-100">
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                          Suggested Next Questions:
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {msg.data.suggested_followups.map((sug, i) => (
                            <button
                              key={i}
                              onClick={() => handleAsk(sug)}
                              disabled={isLoading}
                              className="text-[11px] px-2.5 py-1 rounded-full bg-indigo-50/70 hover:bg-indigo-100 text-indigo-700 font-medium border border-indigo-200/60 transition-all text-left cursor-pointer disabled:opacity-50"
                            >
                              {sug}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Advisory Disclaimer - ONLY rendered for explicit formal reports */}
                    {isFormal && msg.data?.disclaimer && (
                      <div className="text-[10px] text-slate-400 italic pt-2 border-t border-slate-100 flex items-center justify-between">
                        <span>{msg.data.disclaimer}</span>
                        <span>Verified Telemetry</span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {msg.sender === 'user' && (
                <div className="w-8 h-8 rounded-xl bg-slate-800 text-white flex items-center justify-center shrink-0 shadow-sm">
                  <User className="w-4 h-4 text-slate-200" />
                </div>
              )}
            </div>
          );
        })}

        {/* Loading Indicator */}
        {isLoading && (
          <div className="flex gap-3 justify-start items-center">
            <div className="w-8 h-8 rounded-xl bg-indigo-600 text-white flex items-center justify-center shrink-0 animate-pulse shadow-sm shadow-indigo-600/30">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-white border border-indigo-100 rounded-2xl px-5 py-3 shadow-xs flex items-center gap-3">
              <RefreshCw className="w-4 h-4 text-indigo-600 animate-spin" />
              <div className="space-y-0.5">
                <p className="text-xs font-bold text-slate-800">Analyzing driver evidence...</p>
                <p className="text-[10px] text-slate-400">Querying verified telemetry and formulating a clear response</p>
              </div>
            </div>
          </div>
        )}

        <div ref={chatBottomRef} />
      </div>

      {/* Preset Suggestion Chips */}
      <div className="px-6 py-3 bg-white border-t border-slate-100">
        <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
          <HelpCircle className="w-3.5 h-3.5 text-indigo-500" /> Common Fleet Questions
        </p>
        <div className="flex flex-wrap gap-2">
          {PRESET_QUESTIONS.map((q, idx) => (
            <button
              key={idx}
              onClick={() => handleAsk(q)}
              disabled={isLoading}
              className="text-xs font-medium px-3 py-1.5 rounded-full bg-slate-50 hover:bg-indigo-50 text-slate-700 hover:text-indigo-700 border border-slate-200 hover:border-indigo-200 transition-all text-left cursor-pointer disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Input Form with Multi-line Textarea and Enter to Send */}
      <form
        onSubmit={e => {
          e.preventDefault();
          handleAsk();
        }}
        className="p-4 bg-slate-50 border-t border-slate-200 flex items-center gap-3"
      >
        <textarea
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleAsk();
            }
          }}
          placeholder={`Ask about ${driverName || driverId}'s safety (e.g. 'What happened in the last 30 minutes?')... Enter to send, Shift+Enter for newline`}
          disabled={isLoading}
          rows={2}
          className="flex-1 bg-white text-xs text-slate-900 border border-slate-200 rounded-xl px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all placeholder:text-slate-400 disabled:opacity-60 resize-none shadow-2xs"
        />

        <button
          type="submit"
          disabled={isLoading || !question.trim()}
          className="px-5 py-3 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-bold rounded-xl flex items-center gap-2 shadow-md shadow-indigo-600/20 transition-all shrink-0 cursor-pointer disabled:cursor-not-allowed h-full"
        >
          {isLoading ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
          <span>Ask</span>
        </button>
      </form>

      {/* Event Details Modal for Clickable Evidence Links */}
      {isModalOpen && modalEvent && (
        <EventDetailModal
          isOpen={isModalOpen}
          event={modalEvent}
          onClose={() => {
            setIsModalOpen(false);
            setModalEvent(null);
          }}
        />
      )}
    </div>
  );
}
