"use client";

import { useCallback, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";

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
      <Card className="bg-zinc-900 border-zinc-800">
        <CardContent className="flex flex-col items-center justify-center py-16">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-600 border-t-zinc-200" />
          <p className="mt-4 text-sm text-zinc-400">{loadingMessage || "Processing..."}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card
      className={`bg-zinc-900 border-2 border-dashed transition-colors cursor-pointer ${
        isDragging ? "border-zinc-400 bg-zinc-800" : "border-zinc-700 hover:border-zinc-500"
      }`}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      onClick={() => document.getElementById("file-input")?.click()}
    >
      <CardContent className="flex flex-col items-center justify-center py-16">
        <p className="text-lg font-medium text-zinc-300">
          Drop your campaign Excel file here
        </p>
        <p className="mt-2 text-sm text-zinc-500">
          or click to browse (.xlsx)
        </p>
        <input
          id="file-input"
          type="file"
          accept=".xlsx,.xls"
          onChange={handleFileSelect}
          className="hidden"
        />
      </CardContent>
    </Card>
  );
}
