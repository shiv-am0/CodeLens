"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";

import AISettingsModal from "@/components/settings/AISettingsModal";
import { api } from "@/services/api";
import type { AIConfigurationStatus } from "@/types";

type AfterConfigured = () => void | Promise<void>;

interface AIConfigurationContextValue {
  status: AIConfigurationStatus | null;
  openSettings: (afterConfigured?: AfterConfigured) => void;
  ensureConfigured: (afterConfigured?: AfterConfigured) => Promise<boolean>;
  refreshStatus: () => Promise<AIConfigurationStatus>;
}

const AIConfigurationContext = createContext<AIConfigurationContextValue | null>(null);

export function AIConfigurationProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AIConfigurationStatus | null>(null);
  const [loadError, setLoadError] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [afterConfigured, setAfterConfigured] = useState<AfterConfigured | null>(null);

  const refreshStatus = useCallback(async () => {
    setLoadError("");
    try {
      const nextStatus = await api.aiSettings.get();
      setStatus(nextStatus);
      return nextStatus;
    } catch (error) {
      setLoadError(
        error instanceof Error ? error.message : "Unable to load AI configuration"
      );
      throw error;
    }
  }, []);

  const openSettings = useCallback(
    (callback?: AfterConfigured) => {
      setAfterConfigured(() => callback || null);
      setIsOpen(true);
      void refreshStatus();
    },
    [refreshStatus]
  );

  const ensureConfigured = useCallback(
    async (callback?: AfterConfigured) => {
      const currentStatus = await refreshStatus();
      if (currentStatus.configured) {
        return true;
      }
      openSettings(callback);
      return false;
    },
    [openSettings, refreshStatus]
  );

  const handleSaved = useCallback(
    (nextStatus: AIConfigurationStatus) => {
      setStatus(nextStatus);
      setIsOpen(false);
      const callback = afterConfigured;
      setAfterConfigured(null);
      if (callback) {
        void callback();
      }
    },
    [afterConfigured]
  );

  const closeSettings = useCallback(() => {
    setIsOpen(false);
    setAfterConfigured(null);
  }, []);

  const value = useMemo(
    () => ({ status, openSettings, ensureConfigured, refreshStatus }),
    [status, openSettings, ensureConfigured, refreshStatus]
  );

  return (
    <AIConfigurationContext.Provider value={value}>
      {children}
      <AISettingsModal
        open={isOpen}
        status={status}
        loadError={loadError}
        onRetry={() => void refreshStatus()}
        onClose={closeSettings}
        onSaved={handleSaved}
      />
    </AIConfigurationContext.Provider>
  );
}

export function useAIConfiguration() {
  const context = useContext(AIConfigurationContext);
  if (!context) {
    throw new Error("useAIConfiguration must be used inside AIConfigurationProvider");
  }
  return context;
}
