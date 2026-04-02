"use client";

import { useCallback, useState } from "react";

interface UploadZoneProps {
  onUpload: (file: File) => void;
  isLoading: boolean;
  loadingMessage?: string;
}

export function UploadZone({ onUpload, isLoading, loadingMessage }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file && (file.name.endsWith(".xlsx") || file.name.endsWith(".xls"))) {
        onUpload(file);
      }
    },
    [onUpload]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) onUpload(file);
    },
    [onUpload]
  );

  if (isLoading) {
    return (
      <div className="rounded-lg bg-[oklch(0.2_0.005_265)] border border-[oklch(1_0_0/8%)] flex flex-col items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#1a73e8]/30 border-t-[#1a73e8]" />
        <p className="mt-4 text-sm text-[#9aa0a6]">{loadingMessage || "Processing..."}</p>
      </div>
    );
  }

  return (
    <div
      className={`rounded-lg border-2 border-dashed transition-colors cursor-pointer py-20 flex flex-col items-center justify-center ${
        isDragging
          ? "border-[#1a73e8] bg-[#1a73e8]/5"
          : "border-[oklch(1_0_0/15%)] bg-[oklch(0.18_0.005_265)] hover:border-[oklch(1_0_0/25%)]"
      }`}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      onClick={() => document.getElementById("file-input")?.click()}
    >
      <div className="h-12 w-12 rounded-full bg-[#1a73e8]/10 flex items-center justify-center mb-4">
        <svg className="h-6 w-6 text-[#8ab4f8]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
      </div>
      <p className="text-base font-medium text-[#e8eaed]">
        Drop your campaign Excel file here
      </p>
      <p className="mt-1.5 text-sm text-[#9aa0a6]">
        or click to browse (.xlsx)
      </p>
      <input
        id="file-input"
        type="file"
        accept=".xlsx,.xls"
        onChange={handleFileSelect}
        className="hidden"
      />
    </div>
  );
}
