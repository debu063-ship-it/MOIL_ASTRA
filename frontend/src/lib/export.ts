import jsPDF from 'jspdf';
import * as XLSX from 'xlsx';
import { 
  ZoneProperties, 
  ProductionData, 
  CorrectiveAction, 
  ShapData, 
  WhatIfParameters, 
  WhatIfResult,
  LayerDefinition 
} from '@/types';

export interface ExportData {
  zone: ZoneProperties | null;
  production: ProductionData | null;
  actions: CorrectiveAction[];
  actionStatuses: Record<string, string>;
  shap: ShapData | null;
  whatIf: WhatIfParameters;
  whatIfResult: WhatIfResult;
  activeLayers: LayerDefinition[];
  mapCanvas?: HTMLCanvasElement | null;
}

export async function exportToPdf(data: ExportData): Promise<void> {
  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4'
  });

  const pageWidth = doc.internal.pageSize.getWidth();
  let currentY = 15;

  // Header Banner
  doc.setFillColor(11, 15, 25); // Dark blue #0b0f19
  doc.rect(0, 0, pageWidth, 28, 'F');

  doc.setTextColor(56, 189, 248); // Cyan
  doc.setFontSize(16);
  doc.setFont('helvetica', 'bold');
  doc.text('MOIL LIMITED — MANGANESE AI & SPACE INTELLIGENCE REPORT', 14, 12);

  doc.setTextColor(203, 213, 225);
  doc.setFontSize(9);
  doc.setFont('helvetica', 'normal');
  doc.text(`Balaghat Mining Lease (ML-04) | Zone: ${data.zone?.id || 'Overview'} - ${data.zone?.name || 'All Sectors'}`, 14, 18);
  doc.text(`Generated: ${new Date().toLocaleString()} | Compliance: IBM / JORC Provenance Protocols`, 14, 23);

  currentY = 34;

  // Map Screenshot if available
  if (data.mapCanvas) {
    try {
      const imgData = data.mapCanvas.toDataURL('image/png', 0.95);
      const imgWidth = pageWidth - 28;
      const imgHeight = (data.mapCanvas.height / data.mapCanvas.width) * imgWidth;
      const clampedHeight = Math.min(65, imgHeight);

      doc.setDrawColor(56, 189, 248);
      doc.setLineWidth(0.4);
      doc.rect(13.8, currentY - 0.2, imgWidth + 0.4, clampedHeight + 0.4);
      doc.addImage(imgData, 'PNG', 14, currentY, imgWidth, clampedHeight);
      
      // Caption with active layers
      currentY += clampedHeight + 4;
      doc.setFontSize(7.5);
      doc.setTextColor(100, 116, 139);
      const layerTags = data.activeLayers.map(l => `${l.label} ${l.badge}`).join(', ');
      doc.text(`3D Geospatial Capture with Active Layers: ${layerTags}`, 14, currentY);
      currentY += 6;
    } catch (e) {
      console.warn('Could not add canvas image to PDF:', e);
    }
  }

  // Section 1: Zone Prospectivity & Ore Reserve Summary
  doc.setFontSize(11);
  doc.setTextColor(15, 23, 42);
  doc.setFont('helvetica', 'bold');
  doc.text('1. ZONE PROSPECTIVITY & ESTIMATED RESERVES', 14, currentY);
  currentY += 5;

  doc.setFontSize(8.5);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(51, 65, 85);

  const col1 = 14;
  const col2 = 80;
  const col3 = 140;

  doc.text(`• Probability: ${(data.zone ? data.zone.probability * 100 : 89).toFixed(1)}% [MODELED]`, col1, currentY);
  doc.text(`• Estimated Reserves: ${data.zone ? data.zone.estimatedReserveTons.toLocaleString() : '2,150,000'} MT`, col2, currentY);
  doc.text(`• Average Grade: ${data.zone?.avgGrade || '46.2% Mn'}`, col3, currentY);
  currentY += 5;

  doc.text(`• Strike Length: ${data.zone?.strikeLengthMeters || 850}m`, col1, currentY);
  doc.text(`• Overburden: ${data.zone?.overburdenThickness || '28m'}`, col2, currentY);
  doc.text(`• Confidence Level: ${((data.zone?.confidence || 0.94) * 100).toFixed(0)}%`, col3, currentY);
  currentY += 5;
  doc.text(`• Mapped Area: ${data.zone?.areaHectares?.toLocaleString('en-IN', { maximumFractionDigits: 1 }) || 'N/A'} ha`, col1, currentY);
  currentY += 8;

  // Section 2: Production Forecast & Shortfall Prediction
  doc.setFontSize(11);
  doc.setTextColor(15, 23, 42);
  doc.setFont('helvetica', 'bold');
  doc.text('2. PRODUCTION FORECAST & SHORTFALL ANALYSIS [MODELED]', 14, currentY);
  currentY += 5;

  doc.setFontSize(8.5);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(51, 65, 85);

  const targetMT = data.production?.metadata.monthlyTargetMT || 45000;
  const shortfallMT = data.whatIfResult.shortfallMT;
  const riskScore = data.whatIfResult.adjustedRiskScore;
  const riskLevel = data.whatIfResult.adjustedRiskLevel;

  doc.text(`• Monthly Target: ${targetMT.toLocaleString()} MT`, col1, currentY);
  doc.text(`• Forecast Production: ${data.whatIfResult.netProductionForecastMT.toLocaleString()} MT`, col2, currentY);
  doc.text(`• Predicted Shortfall: ${shortfallMT.toLocaleString()} MT (${((shortfallMT / targetMT) * 100).toFixed(1)}%)`, col3, currentY);
  currentY += 5;

  doc.text(`• Operational Risk Gauge: ${riskScore} / 100 [Risk Level: ${riskLevel}]`, col1, currentY);
  doc.text(`• Key Risk Drivers: Monsoon Inundation (4,500 MT), Equipment Downtime (2,600 MT)`, col2, currentY);
  currentY += 8;

  // Section 3: Explainable AI (SHAP Feature Importances)
  doc.setFontSize(11);
  doc.setTextColor(15, 23, 42);
  doc.setFont('helvetica', 'bold');
  doc.text('3. EXPLAINABLE AI (XAI) ATTRIBUTION [MODELED / SHAP]', 14, currentY);
  currentY += 5;

  doc.setFontSize(8);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(71, 85, 105);

  if (data.shap?.features) {
    data.shap.features.slice(0, 4).forEach(feat => {
      doc.text(`• ${feat.name} (${feat.category}): Relative Importance ${feat.importancePct}% [SHAP Value: ${feat.shapValue > 0 ? '+' : ''}${feat.shapValue}]`, col1, currentY);
      currentY += 4.5;
    });
  }
  doc.text(`Attribution Rationale: ${data.shap?.plainLanguageExplanation?.slice(0, 160) || ''}...`, col1, currentY, { maxWidth: pageWidth - 28 });
  currentY += 9;

  // Section 4: What-If Simulator Scenario
  doc.setFontSize(11);
  doc.setTextColor(15, 23, 42);
  doc.setFont('helvetica', 'bold');
  doc.text('4. WHAT-IF SIMULATION SCENARIO [MODELED]', 14, currentY);
  currentY += 5;

  doc.setFontSize(8.5);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(51, 65, 85);
  doc.text(`• Blast Delay: ${data.whatIf.blastDelay} days`, col1, currentY);
  doc.text(`• Equipment Units Delta: ${data.whatIf.equipmentCount > 0 ? '+' : ''}${data.whatIf.equipmentCount} units`, col2, currentY);
  doc.text(`• Rainfall Delta: ${data.whatIf.rainfallChange > 0 ? '+' : ''}${data.whatIf.rainfallChange}%`, col3, currentY);
  currentY += 5;
  doc.text(`• Simulated Output Impact: ${data.whatIfResult.deltaMT > 0 ? '+' : ''}${data.whatIfResult.deltaMT.toLocaleString()} MT | Net Risk Delta: ${data.whatIfResult.deltaRiskScore > 0 ? '+' : ''}${data.whatIfResult.deltaRiskScore.toFixed(1)} pts`, col1, currentY);
  currentY += 8;

  // Section 5: Corrective Actions Status
  doc.setFontSize(11);
  doc.setTextColor(15, 23, 42);
  doc.setFont('helvetica', 'bold');
  doc.text('5. ACTIONABLE INTERVENTIONS & STATUS', 14, currentY);
  currentY += 5;

  data.actions.forEach(action => {
    const status = data.actionStatuses[action.id] || action.status || 'pending';
    const statusText = status.toUpperCase();

    doc.setFontSize(8.5);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(status === 'accepted' ? 22 : status === 'ignored' ? 148 : 217, status === 'accepted' ? 163 : status === 'ignored' ? 163 : 119, status === 'accepted' ? 74 : status === 'ignored' ? 184 : 6);
    doc.text(`[${statusText}] ${action.title}`, 14, currentY);
    currentY += 4.2;

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    doc.setTextColor(71, 85, 105);
    doc.text(`Expected Impact: +${action.expectedImpactMT.toLocaleString()} MT | Risk Reduction: -${action.riskReductionPct}% | Est. Cost: ${action.costEstimateINR} | Lead Time: ${action.leadTimeDays}d`, 18, currentY);
    currentY += 5;
  });

  // Footer
  doc.setFontSize(7);
  doc.setTextColor(148, 163, 184);
  doc.text('MOIL Limited Central Geospatial AI Platform | Confidential & Proprietary Operations Report | Generated via OrePulse', 14, 290);

  doc.save(`MOIL_Manganese_AI_Report_${data.zone?.id || 'Overview'}_${Date.now()}.pdf`);
}

export function exportToExcel(data: ExportData): void {
  const wb = XLSX.utils.book_new();

  // Sheet 1: Zone Summary
  const zoneSummaryData = [
    ["Parameter", "Value", "Data Provenance"],
    ["Zone ID", data.zone?.id || "GLOBAL", "[REAL]"],
    ["Zone Name", data.zone?.name || "Central Lode Deep (Bharweli Main)", "[REAL]"],
    ["Manganese Probability", `${((data.zone?.probability || 0.89) * 100).toFixed(1)}%`, "[MODELED]"],
    ["Estimated Reserves (MT)", data.zone?.estimatedReserveTons || 2150000, "[MODELED]"],
    ["Mapped Prospectivity Area (ha)", data.zone?.areaHectares ?? "N/A", "[MODELED / GEOJSON]"],
    ["Average Grade", data.zone?.avgGrade || "46.2% Mn", "[REAL / ASSAY]"],
    ["Overburden Thickness", data.zone?.overburdenThickness || "28m", "[MODELED]"],
    ["Confidence Index", `${((data.zone?.confidence || 0.94) * 100).toFixed(0)}%`, "[MODELED]"],
    ["What-If Blast Delay (Days)", data.whatIf.blastDelay, "[USER SIMULATION]"],
    ["What-If Equipment Delta", data.whatIf.equipmentCount, "[USER SIMULATION]"],
    ["What-If Rainfall Delta", `${data.whatIf.rainfallChange}%`, "[USER SIMULATION]"],
    ["Simulated Net Forecast (MT)", data.whatIfResult.netProductionForecastMT, "[MODELED]"],
    ["Simulated Shortfall (MT)", data.whatIfResult.shortfallMT, "[MODELED]"],
    ["Simulated Risk Score", data.whatIfResult.adjustedRiskScore, "[MODELED]"]
  ];
  const wsZone = XLSX.utils.aoa_to_sheet(zoneSummaryData);
  XLSX.utils.book_append_sheet(wb, wsZone, "Zone Summary");

  // Sheet 2: Monthly Forecast
  if (data.production?.monthly) {
    const forecastRows = [
      ["Month", "Target (MT)", "Actual Production (MT)", "Forecast (MT)", "Lower 95% CI (MT)", "Upper 95% CI (MT)", "Data Source"]
    ];
    data.production.monthly.forEach(m => {
      forecastRows.push([
        m.month,
        m.target.toString(),
        m.actual !== null ? m.actual.toString() : "N/A (Future)",
        m.forecast.toString(),
        m.lowerCI.toString(),
        m.upperCI.toString(),
        m.actual !== null ? "[REAL]" : "[MODELED]"
      ]);
    });
    const wsForecast = XLSX.utils.aoa_to_sheet(forecastRows);
    XLSX.utils.book_append_sheet(wb, wsForecast, "Monthly Production");
  }

  // Sheet 3: Corrective Actions
  const actionRows = [
    ["Action ID", "Title", "Category", "Expected Impact (MT)", "Risk Reduction (%)", "Estimated Cost", "Lead Time (Days)", "Decision Status", "Provenance"]
  ];
  data.actions.forEach(a => {
    actionRows.push([
      a.id,
      a.title,
      a.category,
      a.expectedImpactMT.toString(),
      `${a.riskReductionPct}%`,
      a.costEstimateINR,
      a.leadTimeDays.toString(),
      (data.actionStatuses[a.id] || a.status).toUpperCase(),
      a.source
    ]);
  });
  const wsActions = XLSX.utils.aoa_to_sheet(actionRows);
  XLSX.utils.book_append_sheet(wb, wsActions, "Corrective Actions");

  // Sheet 4: Active Layers
  const layerRows = [
    ["Layer ID", "Layer Label", "Layer Type", "Data Provenance", "Active in Session"]
  ];
  data.activeLayers.forEach(l => {
    layerRows.push([
      l.id,
      l.label,
      l.type,
      l.badge,
      "YES"
    ]);
  });
  const wsLayers = XLSX.utils.aoa_to_sheet(layerRows);
  XLSX.utils.book_append_sheet(wb, wsLayers, "Active Layers");

  XLSX.writeFile(wb, `MOIL_Manganese_Data_${data.zone?.id || 'Overview'}_${Date.now()}.xlsx`);
}

export function exportToCsv(data: ExportData): void {
  if (!data.production?.monthly) return;

  const rows = [
    ["Month", "Target_MT", "Actual_MT", "Forecast_MT", "LowerCI_MT", "UpperCI_MT", "Source"]
  ];
  data.production.monthly.forEach(m => {
    rows.push([
      m.month,
      m.target.toString(),
      m.actual !== null ? m.actual.toString() : "",
      m.forecast.toString(),
      m.lowerCI.toString(),
      m.upperCI.toString(),
      m.actual !== null ? "[REAL]" : "[MODELED]"
    ]);
  });

  const csvContent = "data:text/csv;charset=utf-8," + rows.map(e => e.join(",")).join("\n");
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", `MOIL_Production_Forecast_${data.zone?.id || 'Overview'}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
