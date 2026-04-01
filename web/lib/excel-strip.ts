import * as XLSX from "xlsx";

const RELEVANT_SHEETS = [
  "Data Analysis Paid Meta",
  "Data Analysis Paid TikTok",
  "Data Analysis Boosting Meta",
  "Data Analysis Boosting TikTok",
];

/**
 * Strips an Excel file to only the 4 "Data Analysis" sheets the backend needs,
 * with raw data only (no formatting, charts, images).
 * Reduces a 7.6MB file to ~50-200KB, well under Vercel's 4.5MB body limit.
 */
export async function stripExcel(file: File): Promise<File> {
  const buffer = await file.arrayBuffer();
  const wb = XLSX.read(buffer, { type: "array" });

  const newWb = XLSX.utils.book_new();
  let sheetsFound = 0;

  for (const name of wb.SheetNames) {
    if (!RELEVANT_SHEETS.includes(name)) continue;
    const sheet = wb.Sheets[name];
    const data = XLSX.utils.sheet_to_json<unknown[]>(sheet, { header: 1 });
    const newSheet = XLSX.utils.aoa_to_sheet(data as unknown[][]);
    XLSX.utils.book_append_sheet(newWb, newSheet, name);
    sheetsFound++;
  }

  if (sheetsFound === 0) {
    throw new Error(
      `No matching sheets found. Expected: ${RELEVANT_SHEETS.join(", ")}`
    );
  }

  const out = XLSX.write(newWb, { type: "array", bookType: "xlsx" });
  const blob = new Blob([out], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  return new File([blob], file.name, { type: blob.type });
}
