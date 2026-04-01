import type { UploadResponse, RescoreResponse, ApiError, ActiveFilters } from "./types";
import { parseExcel } from "./excel-strip";

const API_BASE = "/api";

/** Gzip a string using the browser's CompressionStream API. Returns a Blob. */
async function gzipString(str: string): Promise<Blob> {
  const blob = new Blob([str]);
  const cs = new CompressionStream("gzip");
  const stream = blob.stream().pipeThrough(cs);
  return new Response(stream).blob();
}

export async function uploadAndScore(
  file: File,
  onProgress?: (msg: string) => void
): Promise<UploadResponse> {
  onProgress?.("Parsing Excel file...");
  const sheets = await parseExcel(file);
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
  const res = await fetch(`${API_BASE}/rescore`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ upload_id: uploadId, filters }),
  });

  if (!res.ok) {
    const err: { detail: ApiError } = await res.json();
    throw new Error(err.detail?.message || "Rescore failed");
  }

  return res.json();
}
