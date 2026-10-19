import type { TFunction } from "i18next";
import i18n from "../i18n";
import type {
  AnalysisResult,
  CheckResult,
  PhotoMap,
  ViewName,
  Verdict,
} from "../types";
import { formatDateTime, formatFieldDate } from "./format";
import { loadImageElement } from "./images";

export function verdictLabelKey(verdict: Verdict): string {
  return `result.labels.${verdict}`;
}

export function statusLabelKey(status: CheckResult["status"]): string {
  return `status.${status}`;
}

function referenceLabel(result: AnalysisResult, t: TFunction): string {
  return result.reference?.name ?? t("result.reference.none");
}

function checkLine(check: CheckResult, t: TFunction): string {
  const title = t(check.title_key, { defaultValue: check.id });
  const explanation = t(check.explanation_key, {
    ...check.params,
    defaultValue: check.explanation_en,
  });
  return `- ${title}: ${explanation}`;
}

export function buildReportText(
  result: AnalysisResult,
  t: TFunction,
  language: "en" | "ur",
): string {
  const failed = result.checks.filter((check) => check.status === "fail");
  const warned = result.checks.filter((check) => check.status === "warn");
  const lines: string[] = [
    t("report.summaryTitle"),
    `${t("report.verdict")}: ${t(verdictLabelKey(result.verdict))}`,
    `${t("report.productName")}: ${result.fields.product_name ?? "-"}`,
    `${t("report.batch")}: ${result.fields.batch_number ?? "-"}`,
    `${t("report.expiry")}: ${
      formatFieldDate(result.fields.expiry_date, language) ?? "-"
    }`,
    `${t("report.registration")}: ${result.fields.registration_number ?? "-"}`,
    `${t("report.reference")}: ${referenceLabel(result, t)}`,
    `${t("report.score")}: ${result.risk_score} / 100`,
    `${t("report.screened")}: ${formatDateTime(result.created_at, language)}`,
  ];
  if (failed.length) {
    lines.push("", `${t("report.failedTitle")}:`);
    lines.push(...failed.map((check) => checkLine(check, t)));
  }
  if (warned.length) {
    lines.push("", `${t("report.warnedTitle")}:`);
    lines.push(...warned.map((check) => checkLine(check, t)));
  }
  if (!failed.length && !warned.length) {
    lines.push("", t("report.noIssues"));
  }
  lines.push("", t("report.notOfficial"), t("app.disclaimer"));
  if (result.reference?.demo) {
    lines.push(t("report.demo"));
  }
  return lines.join("\n");
}

function pdfColorForVerdict(verdict: Verdict): [number, number, number] {
  if (verdict === "consistent") return [15, 118, 110];
  if (verdict === "suspicious") return [168, 90, 8];
  return [100, 116, 139];
}

export async function generateReportPdf(
  result: AnalysisResult,
  photos: PhotoMap,
): Promise<void> {
  const [{ jsPDF }, { default: autoTable }] = await Promise.all([
    import("jspdf"),
    import("jspdf-autotable"),
  ]);
  const t = i18n.getFixedT("en");
  const doc = new jsPDF({ unit: "mm", format: "a4", compress: true });
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 16;
  const contentWidth = pageWidth - margin * 2;
  const accent = pdfColorForVerdict(result.verdict);

  const pageFooter = () => {
    const pages = doc.getNumberOfPages();
    for (let page = 1; page <= pages; page += 1) {
      doc.setPage(page);
      doc.setFont("helvetica", "normal");
      doc.setFontSize(7.5);
      doc.setTextColor(110, 125, 122);
      doc.text(t("pdf.footerNote"), margin, pageHeight - 13);
      doc.text(t("pdf.notOfficial"), margin, pageHeight - 9);
      doc.text(
        `${t("pdf.page")} ${page} / ${pages}`,
        pageWidth - margin,
        pageHeight - 9,
        { align: "right" },
      );
      doc.setDrawColor(220, 230, 226);
      doc.setLineWidth(0.2);
      doc.line(margin, pageHeight - 17, pageWidth - margin, pageHeight - 17);
    }
  };

  const lastTableY = (): number => {
    const withTable = doc as unknown as {
      lastAutoTable?: { finalY?: number };
    };
    return withTable.lastAutoTable?.finalY ?? 60;
  };

  doc.setFillColor(15, 118, 110);
  doc.rect(0, 0, pageWidth, 38, "F");
  doc.setFillColor(9, 78, 73);
  doc.rect(0, 34, pageWidth, 4, "F");
  doc.setTextColor(255, 255, 255);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(21);
  doc.text(t("app.name"), margin, 16);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.text(t("pdf.title"), margin, 23);
  doc.setFontSize(8);
  doc.setTextColor(214, 243, 237);
  doc.text(
    `${t("pdf.generated")}: ${formatDateTime(result.created_at, "en")} - ${result.analysis_id}`,
    margin,
    30,
  );

  let cursor = 48;
  doc.setFillColor(accent[0], accent[1], accent[2]);
  doc.roundedRect(margin, cursor, contentWidth, 30, 4, 4, "F");
  doc.setTextColor(255, 255, 255);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(17);
  doc.text(t(verdictLabelKey(result.verdict)), margin + 6, cursor + 11);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.text(
    `${t("pdf.score")}: ${result.risk_score} / 100   -   ${t("pdf.confidence")}: ${t(
      `confidence.${result.confidence}.label`,
    )}`,
    margin + 6,
    cursor + 19,
  );
  doc.text(
    `${t("pdf.screened")}: ${formatDateTime(result.created_at, "en")}`,
    margin + 6,
    cursor + 25,
  );
  cursor += 36;

  if (result.reference?.demo) {
    doc.setFillColor(255, 243, 220);
    doc.setDrawColor(240, 199, 126);
    doc.roundedRect(margin, cursor, contentWidth, 11, 2, 2, "FD");
    doc.setTextColor(138, 74, 7);
    doc.setFontSize(8.5);
    doc.text(t("pdf.demo"), margin + 4, cursor + 7);
    cursor += 16;
  }

  const details: [string, string][] = [];
  const addDetail = (label: string, value: string | null | undefined) => {
    if (value && value.trim()) details.push([label, value]);
  };
  addDetail(t("pdf.product"), result.fields.product_name);
  addDetail(t("pdf.strength"), result.fields.strength);
  addDetail(t("pdf.manufacturer"), result.fields.manufacturer);
  addDetail(t("pdf.registration"), result.fields.registration_number);
  addDetail(t("pdf.batch"), result.fields.batch_number);
  addDetail(t("pdf.expiry"), formatFieldDate(result.fields.expiry_date, "en"));
  addDetail(t("pdf.barcode"), result.fields.barcode);
  addDetail(
    t("pdf.reference"),
    result.reference
      ? `${result.reference.name}${result.reference.demo ? " (DEMO)" : ""}`
      : t("result.reference.none"),
  );

  autoTable(doc, {
    startY: cursor,
    margin: { left: margin, right: margin },
    body: details,
    theme: "plain",
    styles: { fontSize: 9, cellPadding: 2, textColor: [30, 50, 46] },
    columnStyles: {
      0: { cellWidth: 45, fontStyle: "bold", textColor: [82, 104, 99] },
      1: { cellWidth: contentWidth - 45 },
    },
  });
  cursor = lastTableY() + 8;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.setTextColor(30, 50, 46);
  doc.text(t("pdf.findings"), margin, cursor);
  cursor += 4;

  const checkRows = result.checks.map((check) => [
    t(check.title_key, { defaultValue: check.id }),
    t(statusLabelKey(check.status)),
    `${check.risk_points} / ${check.weight}`,
  ]);
  autoTable(doc, {
    startY: cursor,
    margin: { left: margin, right: margin },
    head: [[t("pdf.check"), t("pdf.status"), t("pdf.riskPoints")]],
    body: checkRows,
    theme: "striped",
    headStyles: {
      fillColor: [15, 118, 110],
      textColor: [255, 255, 255],
      fontSize: 8.5,
    },
    styles: { fontSize: 8.5, cellPadding: 2.2, textColor: [30, 50, 46] },
    alternateRowStyles: { fillColor: [244, 250, 248] },
    columnStyles: {
      0: { cellWidth: contentWidth - 55 },
      1: { cellWidth: 30 },
      2: { cellWidth: 25, halign: "right" },
    },
    didParseCell: (data) => {
      if (data.section === "body" && data.column.index === 1) {
        const status = result.checks[data.row.index]?.status;
        if (status === "fail") data.cell.styles.textColor = [180, 35, 24];
        else if (status === "warn") data.cell.styles.textColor = [168, 90, 8];
        else if (status === "pass") data.cell.styles.textColor = [15, 118, 110];
      }
    },
  });
  cursor = lastTableY() + 9;

  const photoViews: [ViewName, string][] = [
    ["front", t("pdf.front")],
    ["back", t("pdf.back")],
    ["batch", t("pdf.batchPhoto")],
    ["blister", t("pdf.blisterPhoto")],
  ];
  const availablePhotos = photoViews.filter(([view]) => photos[view]);
  if (availablePhotos.length) {
    if (cursor > pageHeight - 70) {
      doc.addPage();
      cursor = 22;
    }
    doc.setFont("helvetica", "bold");
    doc.setFontSize(12);
    doc.setTextColor(30, 50, 46);
    doc.text(t("pdf.photos"), margin, cursor);
    cursor += 6;
    const slotWidth = (contentWidth - 6) / 2;
    let slot = 0;
    for (const [view, label] of availablePhotos) {
      const data = photos[view];
      if (!data) continue;
      if (slot % 2 === 0 && cursor > pageHeight - 88) {
        doc.addPage();
        cursor = 22;
      }
      const column = slot % 2;
      const boxX = margin + column * (slotWidth + 6);
      try {
        const image = await loadImageElement(data);
        const maxWidth = slotWidth;
        const maxHeight = 62;
        const scale = Math.min(
          maxWidth / image.naturalWidth,
          maxHeight / image.naturalHeight,
        );
        const width = image.naturalWidth * scale;
        const height = image.naturalHeight * scale;
        const x = boxX + (slotWidth - width) / 2;
        doc.setFillColor(243, 249, 247);
        doc.setDrawColor(220, 230, 226);
        doc.roundedRect(boxX, cursor, slotWidth, maxHeight + 4, 2, 2, "FD");
        doc.addImage(data, "JPEG", x, cursor + 2, width, height, undefined, "FAST");
      } catch {
        doc.setFont("helvetica", "normal");
        doc.setFontSize(8);
        doc.setTextColor(110, 125, 122);
        doc.text(t("pdf.noPhotos"), boxX + 4, cursor + 10);
      }
      doc.setFont("helvetica", "normal");
      doc.setFontSize(7.5);
      doc.setTextColor(82, 104, 99);
      doc.text(label, boxX, cursor + 68);
      slot += 1;
      if (slot % 2 === 0) cursor += 72;
    }
    if (slot % 2 !== 0) cursor += 72;
  }

  if (cursor > pageHeight - 50) {
    doc.addPage();
    cursor = 22;
  } else {
    cursor += 2;
  }
  const disclaimer = doc.splitTextToSize(
    t("pdf.disclaimer"),
    contentWidth - 8,
  );
  const disclaimerHeight = disclaimer.length * 4 + 9;
  doc.setFillColor(255, 247, 236);
  doc.setDrawColor(238, 205, 150);
  doc.roundedRect(margin, cursor, contentWidth, disclaimerHeight, 2, 2, "FD");
  doc.setFont("helvetica", "bold");
  doc.setFontSize(8);
  doc.setTextColor(138, 74, 7);
  doc.text(t("result.disclaimerLabel"), margin + 4, cursor + 6);
  doc.setFont("helvetica", "normal");
  doc.text(disclaimer, margin + 4, cursor + 10.5);

  pageFooter();
  doc.save(`DawaiCheck-report-${result.analysis_id}.pdf`);
}
