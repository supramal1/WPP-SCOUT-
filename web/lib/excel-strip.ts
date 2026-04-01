import * as XLSX from "xlsx";

/**
 * Strips an Excel file down to raw data only (no formatting, charts, images).
 * This reduces a 7.6MB file to ~100KB, staying under Vercel's 4.5MB body limit.
 */
export async function stripExcel(file: File): Promise<File> {
  const buffer = await file.arrayBuffer();
  const wb = XLSX.read(buffer, { type: "array" });

  const newWb = XLSX.utils.book_new();
  for (const name of wb.SheetNames) {
    const sheet = wb.Sheets[name];
    const data = XLSX.utils.sheet_to_json<unknown[]>(sheet, { header: 1 });
    const newSheet = XLSX.utils.aoa_to_sheet(data as unknown[][]);
    XLSX.utils.book_append_sheet(newWb, newSheet, name);
  }

  const out = XLSX.write(newWb, { type: "array", bookType: "xlsx" });
  const blob = new Blob([out], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  return new File([blob], file.name, { type: blob.type });
}
