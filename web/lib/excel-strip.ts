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
/** Trim trailing null/undefined from a row and skip fully-empty rows. */
function trimRow(row: (string | number | null)[]): (string | number | null)[] | null {
  let last = row.length - 1;
  while (last >= 0 && (row[last] === null || row[last] === undefined || row[last] === "")) {
    last--;
  }
  return last < 0 ? null : row.slice(0, last + 1);
}

export async function parseExcel(file: File): Promise<ParsedSheets> {
  const buffer = await file.arrayBuffer();
  const wb = XLSX.read(buffer, { type: "array" });

  const sheets: ParsedSheets = {};
  for (const name of wb.SheetNames) {
    if (!RELEVANT_SHEETS.includes(name)) continue;
    const sheet = wb.Sheets[name];
    const raw = XLSX.utils.sheet_to_json<(string | number | null)[]>(sheet, {
      header: 1,
      defval: null,
    });
    const trimmed: (string | number | null)[][] = [];
    for (const row of raw) {
      const t = trimRow(row);
      if (t) trimmed.push(t);
    }
    sheets[name] = trimmed;
  }

  if (Object.keys(sheets).length === 0) {
    throw new Error(
      `No matching sheets found. Expected: ${RELEVANT_SHEETS.join(", ")}`
    );
  }

  return sheets;
}
