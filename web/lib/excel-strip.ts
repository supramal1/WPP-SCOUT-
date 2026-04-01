import * as XLSX from "xlsx";

const RELEVANT_SHEETS = [
  "Data Analysis Paid Meta",
  "Data Analysis Paid TikTok",
  "Data Analysis Boosting Meta",
  "Data Analysis Boosting TikTok",
];

export interface ParsedSheets {
  [sheetName: string]: (string | number | null)[][];
}

/**
 * Parses an Excel file in the browser and extracts only the relevant
 * "Data Analysis" sheets as raw arrays. Returns JSON-serializable data
 * instead of a File, avoiding the 4.5MB Vercel body limit.
 */
export async function parseExcel(file: File): Promise<ParsedSheets> {
  const buffer = await file.arrayBuffer();
  const wb = XLSX.read(buffer, { type: "array" });

  const sheets: ParsedSheets = {};
  for (const name of wb.SheetNames) {
    if (!RELEVANT_SHEETS.includes(name)) continue;
    const sheet = wb.Sheets[name];
    sheets[name] = XLSX.utils.sheet_to_json<(string | number | null)[]>(sheet, {
      header: 1,
      defval: null,
    });
  }

  if (Object.keys(sheets).length === 0) {
    throw new Error(
      `No matching sheets found. Expected: ${RELEVANT_SHEETS.join(", ")}`
    );
  }

  return sheets;
}
