import type { UploadResponse, RescoreResponse, ApiError, ActiveFilters } from "./types";

const API_BASE = "/api";

export async function uploadAndScore(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/upload-and-score`, {
    method: "POST",
    body: formData,
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
