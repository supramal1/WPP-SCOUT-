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
      <div className="rounded-lg bg-[#f8f9fa] border border-[#dadce0] flex flex-col items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#1a73e8]/30 border-t-[#1a73e8]" />
        <p className="mt-4 text-sm text-[#5f6368]">{loadingMessage || "Processing..."}</p>
      </div>
    );
  }

  return (
    <div
      className={`rounded-lg border-2 border-dashed transition-colors cursor-pointer py-20 flex flex-col items-center justify-center ${
        isDragging
          ? "border-[#1a73e8] bg-[#e8f0fe]"
          : "border-[#dadce0] bg-[#f8f9fa] hover:border-[#80868b] hover:bg-[#f1f3f4]"
      }`}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      onClick={() => document.getElementById("file-input")?.click()}
    >
      <div className="h-12 w-12 rounded-full bg-[#e8f0fe] flex items-center justify-center mb-4">
        <svg className="h-6 w-6 text-[#1a73e8]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
      </div>
      <p className="text-base font-medium text-[#202124]">
        Drop your campaign Excel file here
      </p>
      <p className="mt-1.5 text-sm text-[#5f6368]">
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
