import type { UploadResponse, RescoreResponse, ApiError, ActiveFilters } from "./types";
import { parseExcel } from "./excel-strip";

const API_BASE = "/api";

export async function uploadAndScore(
  file: File,
  onProgress?: (msg: string) => void
): Promise<UploadResponse> {
  onProgress?.("Parsing Excel file...");
  const sheets = await parseExcel(file);
  const sheetNames = Object.keys(sheets);
  onProgress?.(`Scoring ${sheetNames.length} sheet(s)...`);

  const body = JSON.stringify({ sheets });
  const sizeMB = (body.length / (1024 * 1024)).toFixed(1);
  onProgress?.(`Uploading ${sizeMB}MB and scoring...`);

  const res = await fetch(`${API_BASE}/upload-and-score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
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
