import type { UploadResponse, RescoreResponse, ApiError, ActiveFilters } from "./types";
import { stripExcel } from "./excel-strip";

const API_BASE = "/api";

export async function uploadAndScore(
  file: File,
  onProgress?: (msg: string) => void
): Promise<UploadResponse> {
  onProgress?.("Preparing file...");
  const stripped = await stripExcel(file);
  const sizeMB = (stripped.size / (1024 * 1024)).toFixed(1);
  onProgress?.(`Uploading ${sizeMB}MB and scoring...`);

  const res = await fetch(`${API_BASE}/upload-and-score`, {
    method: "POST",
    body: (() => {
      const fd = new FormData();
      fd.append("file", stripped);
      return fd;
    })(),
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
