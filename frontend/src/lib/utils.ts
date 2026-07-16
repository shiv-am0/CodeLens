import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function getStatusColor(status: string): string {
  switch (status) {
    case "completed": return "bg-emerald-500";
    case "analyzing":
    case "embedding":
    case "indexing":
    case "cloning": return "bg-amber-500";
    case "failed": return "bg-red-500";
    default: return "bg-surface-500";
  }
}
