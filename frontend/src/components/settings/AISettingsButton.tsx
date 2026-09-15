"use client";

import { Settings } from "lucide-react";

import { cn } from "@/lib/utils";
import { useAIConfiguration } from "@/components/settings/AIConfigurationProvider";


export default function AISettingsButton({
  compact = false,
  className,
}: {
  compact?: boolean;
  className?: string;
}) {
  const { openSettings, status } = useAIConfiguration();

  return (
    <button
      type="button"
      onClick={() => openSettings()}
      className={cn(
        "flex items-center gap-2 text-surface-400 hover:text-surface-100 transition-colors",
        className
      )}
      aria-label="Configure AI settings"
    >
      <span className="relative">
        <Settings className="w-5 h-5" />
        {status && !status.configured && (
          <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-warning" />
        )}
      </span>
      {!compact && <span>AI Settings</span>}
    </button>
  );
}
