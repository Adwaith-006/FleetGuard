import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import { calculateSafetyScore } from './safetyScore';
import { formatDateTime } from './dateUtils';

export function downloadPDFReport({ driver = {}, vehicle = {}, events = [], dateRange = 'All Time', sessionId = 'All Recorded Sessions' }) {
  try {
    const doc = new jsPDF();
    const safeEvents = Array.isArray(events) ? events : [];
    const scoreInfo = calculateSafetyScore(safeEvents);
    const nowStr = new Date().toISOString().split('T')[0];

    const driverName = driver.name || driver.driver_name || 'Prototype Driver';
    const driverId = driver.id || driver.driver_id || 'DRV001';
    const driverLicense = driver.license || 'DL-DEMO-2026';

    const vehicleNo = vehicle.vehicleNo || vehicle.vehicle_no || 'Prototype Vehicle';
    const vehicleId = vehicle.id || vehicle.vehicle_id || 'VEH001';

    // Header Banner
    doc.setFillColor(30, 41, 59); // slate-800
    doc.rect(0, 0, 210, 28, 'F');
    
    doc.setTextColor(255, 255, 255);
    doc.setFontSize(16);
    doc.setFont('helvetica', 'bold');
    doc.text('DRIVER SAFETY PERFORMANCE REPORT', 14, 18);

    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    doc.text(`Generated: ${new Date().toLocaleDateString()}`, 150, 18);

    // Driver & Vehicle Profile Box
    doc.setLineWidth(0.3);
    doc.setDrawColor(203, 213, 225);
    doc.setFillColor(248, 250, 252);
    doc.rect(14, 34, 182, 38, 'FD');

    doc.setTextColor(30, 41, 59);
    doc.setFontSize(10);
    doc.setFont('helvetica', 'bold');
    doc.text('Driver Information', 20, 43);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(9);
    doc.text(`Driver Name: ${driverName}`, 20, 50);
    doc.text(`Driver ID: ${driverId}`, 20, 56);
    doc.text(`License No: ${driverLicense}`, 20, 62);

    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10);
    doc.text('Vehicle & Test Session', 105, 43);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8.5);
    doc.text(`Vehicle: ${vehicleNo}`, 105, 50);
    doc.text(`Session ID: ${sessionId}`, 105, 56);
    doc.text(`Reporting Period: ${dateRange}`, 105, 62);

    // Safety Score Box
    doc.setFillColor(
      scoreInfo.score >= 90 ? 236 : scoreInfo.score >= 70 ? 254 : 254, 
      scoreInfo.score >= 90 ? 253 : scoreInfo.score >= 70 ? 243 : 226, 
      scoreInfo.score >= 90 ? 245 : scoreInfo.score >= 70 ? 199 : 226
    );
    doc.rect(14, 78, 182, 22, 'F');
    
    doc.setFontSize(12);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(15, 23, 42);
    doc.text(`Safety Score: ${scoreInfo.score} / 100`, 20, 92);

    doc.setFontSize(11);
    doc.text(`Status: ${scoreInfo.status}`, 130, 92);

    // Event Summary Table
    const drowsinessCount = safeEvents.filter(e => e.event_type === 'DROWSINESS').length;
    const yawningCount = safeEvents.filter(e => e.event_type === 'YAWNING').length;
    const phoneCount = safeEvents.filter(e => e.event_type === 'PHONE_DETECTED' || e.event_type === 'PHONE_USAGE').length;
    const criticalCount = safeEvents.filter(e => e.severity === 'CRITICAL' || e.status === 'UNSAFE' || e.status === 'HIGH_RISK').length;

    autoTable(doc, {
      startY: 106,
      head: [['Total Events', 'Drowsiness Events', 'Yawning Events', 'Phone Usage Events', 'Critical Alerts']],
      body: [[safeEvents.length, drowsinessCount, yawningCount, phoneCount, criticalCount]],
      theme: 'grid',
      headStyles: { fillColor: [51, 65, 85], fontSize: 9, halign: 'center' },
      bodyStyles: { fontSize: 10, halign: 'center', fontStyle: 'bold' }
    });

    const summaryFinalY = doc.lastAutoTable ? doc.lastAutoTable.finalY : 125;

    // Event History Table
    doc.setFontSize(11);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(30, 41, 59);
    doc.text('Safety Event History Log', 14, summaryFinalY + 12);

    const historyData = safeEvents.map(evt => [
      formatDateTime(evt.start_time || evt.timestamp),
      evt.event_type || 'EVENT',
      `${evt.duration || 0}s`,
      evt.status || evt.severity || 'OBSERVED',
      evt.metrics?.avg_ear ? `EAR: ${evt.metrics.avg_ear}` : 
      evt.metrics?.max_mar ? `MAR: ${evt.metrics.max_mar}` : 
      evt.metrics?.max_confidence ? `Conf: ${evt.metrics.max_confidence}` :
      evt.confidence ? `Conf: ${evt.confidence}` : '-'
    ]);

    autoTable(doc, {
      startY: summaryFinalY + 16,
      head: [['Date & Time', 'Event Type', 'Duration', 'Objective Status', 'Metrics']],
      body: historyData.length > 0 ? historyData : [['No events recorded for this period', '-', '-', '-', '-']],
      theme: 'striped',
      headStyles: { fillColor: [71, 85, 105], fontSize: 9 },
      bodyStyles: { fontSize: 8.5 }
    });

    // Footer Disclaimer
    doc.setFontSize(8);
    doc.setFont('helvetica', 'italic');
    doc.setTextColor(148, 163, 184);
    doc.text(
      'Notice: Driver Safety Score is an engineering risk estimation based on edge AI monitoring metrics. For human management review.',
      14,
      285
    );

    const safeDriverFilename = driverName.replace(/[^a-zA-Z0-9]/g, '_');
    const filename = `Driver_Safety_Report_${safeDriverFilename}_${nowStr}.pdf`;
    
    doc.save(filename);
    console.log("PDF Report downloaded successfully:", filename);
  } catch (error) {
    console.error("Error generating or downloading PDF report:", error);
    alert("Failed to generate PDF: " + (error.message || error));
  }
}
