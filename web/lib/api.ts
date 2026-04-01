import type { UploadResponse, RescoreResponse, ApiError, ActiveFilters, SplitRow } from "./types";
import { parseExcel } from "./excel-strip";

const API_BASE = "/api";

// Direct backend URL for large payloads — bypasses the Next.js rewrite proxy
// which can timeout or reject large bodies.
const DIRECT_API_BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api`
  : "/api";

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

async function parseErrorResponse(res: Response, fallback: string): Promise<string> {
  try {
    const data = await res.json();
    return data?.detail?.message || data?.message || fallback;
  } catch {
    return `${fallback} (HTTP ${res.status})`;
  }
}

export async function rescore(
  uploadId: string,
  filters: ActiveFilters
): Promise<RescoreResponse> {
  // First attempt: without sheets (fast, small payload)
  const res = await fetch(`${API_BASE}/rescore`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ upload_id: uploadId, filters }),
  });

  if (res.ok) return res.json();

  // If cache expired (404) and we have sheets, retry with sheet data.
  // Use direct API URL to bypass the Next.js rewrite proxy which can
  // timeout on large payloads.
  if (res.status === 404 && _cachedSheets) {
    const retryRes = await fetch(`${DIRECT_API_BASE}/rescore`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ upload_id: uploadId, filters, sheets: _cachedSheets }),
    });

    if (retryRes.ok) return retryRes.json();
    throw new Error(await parseErrorResponse(retryRes, "Rescore failed on retry"));
  }

  throw new Error(await parseErrorResponse(res, "Rescore failed"));
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
