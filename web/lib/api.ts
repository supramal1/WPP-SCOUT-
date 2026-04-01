import type { UploadResponse, RescoreResponse, ApiError, ActiveFilters, SplitRow } from "./types";
import { parseExcel } from "./excel-strip";

const API_BASE = "/api";

/** Gzip a string using the browser's CompressionStream API. Returns a Blob. */
async function gzipString(str: string): Promise<Blob> {
  const blob = new Blob([str]);
  const cs = new CompressionStream("gzip");
  const stream = blob.stream().pipeThrough(cs);
  return new Response(stream).blob();
}

export type SheetData = Record<string, unknown[][]>;

// Module-level storage for parsed sheets — survives across component renders
let _cachedSheets: SheetData | null = null;

export function getCachedSheets(): SheetData | null {
  return _cachedSheets;
}

export async function uploadAndScore(
  file: File,
  onProgress?: (msg: string) => void
): Promise<UploadResponse> {
  onProgress?.("Parsing Excel file...");
  const sheets = await parseExcel(file);
  _cachedSheets = sheets;
  const sheetNames = Object.keys(sheets);
  onProgress?.(`Scoring ${sheetNames.length} sheet(s)...`);

  const json = JSON.stringify({ sheets });
  const jsonMB = (json.length / (1024 * 1024)).toFixed(1);
  onProgress?.(`Compressing ${jsonMB}MB...`);

  const compressed = await gzipString(json);
  const compMB = (compressed.size / (1024 * 1024)).toFixed(1);
  onProgress?.(`Uploading ${compMB}MB (compressed) and scoring...`);

  const res = await fetch(`${API_BASE}/upload-and-score`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Content-Encoding": "gzip",
    },
    body: compressed,
  });

  if (!res.ok) {
    const err: { detail: ApiError } = await res.json();
    throw new Error(err.detail?.message || "Upload failed");
  }

  return res.json();
}

export async function rescore(
  uploadId: string,
  filters: ActiveFilters
): Promise<RescoreResponse> {
  const payload: Record<string, unknown> = { upload_id: uploadId, filters };

  // Include cached sheets so the backend can re-hydrate if in-memory cache expired
  const sheets = _cachedSheets;
  if (sheets) {
    payload.sheets = sheets;
  }

  const json = JSON.stringify(payload);

  // Gzip when payload is large (sheets included)
  const useGzip = json.length > 50_000;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  let body: BodyInit;

  if (useGzip) {
    headers["Content-Encoding"] = "gzip";
    body = await gzipString(json);
  } else {
    body = json;
  }

  const res = await fetch(`${API_BASE}/rescore`, {
    method: "POST",
    headers,
    body,
  });

  if (!res.ok) {
    const err: { detail: ApiError } = await res.json();
    throw new Error(err.detail?.message || "Rescore failed");
  }

  return res.json();
}

export async function fetchSplits(uploadId: string): Promise<SplitRow[]> {
  const res = await fetch(`${API_BASE}/splits`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ upload_id: uploadId }),
  });

  if (!res.ok) {
    throw new Error("Failed to fetch splits");
  }

  const data: { splits: SplitRow[]; meta: { total_rows: number } } = await res.json();
  return data.splits;
}
