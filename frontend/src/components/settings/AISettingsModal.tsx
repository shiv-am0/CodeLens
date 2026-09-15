"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { ChevronDown, Eye, EyeOff, KeyRound, Loader2, Settings, ShieldCheck, X } from "lucide-react";

import { ApiError, api } from "@/services/api";
import type { AIConfigurationStatus } from "@/types";


const CUSTOM_MODEL = "__custom__";

interface AISettingsModalProps {
  open: boolean;
  status: AIConfigurationStatus | null;
  loadError: string;
  onRetry: () => void;
  onClose: () => void;
  onSaved: (status: AIConfigurationStatus) => void;
}

export default function AISettingsModal({
  open,
  status,
  loadError,
  onRetry,
  onClose,
  onSaved,
}: AISettingsModalProps) {
  const [apiKey, setApiKey] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [modelChoice, setModelChoice] = useState("");
  const [customModel, setCustomModel] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [useCustomEncryption, setUseCustomEncryption] = useState(false);
  const [encryptionKey, setEncryptionKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const firstInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;

    const supportedModels = status?.supported_chat_models || [];
    const currentModel = status?.chat_model || supportedModels[0] || "gpt-4o-mini";
    if (supportedModels.includes(currentModel)) {
      setModelChoice(currentModel);
      setCustomModel("");
    } else {
      setModelChoice(CUSTOM_MODEL);
      setCustomModel(currentModel);
    }

    setApiKey("");
    setAdminPassword("");
    setEncryptionKey("");
    setUseCustomEncryption(false);
    setAdvancedOpen(false);
    setError("");
    window.setTimeout(() => firstInputRef.current?.focus(), 0);
  }, [open, status]);

  useEffect(() => {
    if (!open) return;
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !saving) onClose();
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [open, saving, onClose]);

  if (!open) return null;

  const selectedModel = modelChoice === CUSTOM_MODEL ? customModel.trim() : modelChoice;
  const requiresApiKey = !status?.api_key_configured;

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");

    if (requiresApiKey && !apiKey.trim()) {
      setError("Enter an OpenAI API key to complete the initial setup.");
      return;
    }
    if (!selectedModel) {
      setError("Select or enter an OpenAI chat model.");
      return;
    }
    if (!adminPassword) {
      setError("Enter the CodeLens admin password.");
      return;
    }
    if (useCustomEncryption && !encryptionKey.trim()) {
      setError("Enter a Fernet encryption key or use automatic generation.");
      return;
    }

    setSaving(true);
    try {
      const nextStatus = await api.aiSettings.update({
        admin_password: adminPassword,
        api_key: apiKey.trim() || undefined,
        chat_model: selectedModel,
        encryption_key:
          useCustomEncryption && !status?.encryption_initialized
            ? encryptionKey.trim()
            : undefined,
      });
      setApiKey("");
      setAdminPassword("");
      setEncryptionKey("");
      onSaved(nextStatus);
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "Unable to save the AI configuration."
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-surface-950/85 px-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="ai-settings-title"
    >
      <div className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-surface-700 bg-surface-900 shadow-2xl">
        <div className="flex items-start justify-between border-b border-surface-800 p-6">
          <div className="flex gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/10">
              <Settings className="h-5 w-5 text-accent" />
            </div>
            <div>
              <h2 id="ai-settings-title" className="text-xl font-semibold text-surface-100">
                OpenAI configuration
              </h2>
              <p className="mt-1 text-sm text-surface-400">
                Secrets are encrypted by the backend and are never returned to the browser.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="rounded-lg p-2 text-surface-500 hover:bg-surface-800 hover:text-surface-100"
            aria-label="Close AI settings"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {!status ? (
          <div className="flex min-h-52 flex-col items-center justify-center gap-4 p-8 text-center">
            {loadError ? (
              <>
                <p className="text-sm text-red-400">{loadError}</p>
                <button type="button" onClick={onRetry} className="btn-secondary text-sm">
                  Retry
                </button>
              </>
            ) : (
              <>
                <Loader2 className="h-7 w-7 animate-spin text-accent" />
                <p className="text-sm text-surface-400">Loading AI configuration...</p>
              </>
            )}
          </div>
        ) : (
        <form onSubmit={handleSubmit} className="space-y-5 p-6">
          {status.provider === "openai" && status.configured && (
            <div className="flex items-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-400">
              <ShieldCheck className="h-4 w-4" />
              OpenAI is configured. Leave the key blank to keep the existing key.
            </div>
          )}

          <div>
            <label htmlFor="openai-api-key" className="mb-2 block text-sm font-medium text-surface-200">
              OpenAI API key {requiresApiKey && <span className="text-red-400">*</span>}
            </label>
            <div className="relative">
              <KeyRound className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-500" />
              <input
                ref={firstInputRef}
                id="openai-api-key"
                type={showApiKey ? "text" : "password"}
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder={status?.api_key_configured ? "Leave blank to keep the current key" : "sk-..."}
                autoComplete="new-password"
                className="input-field px-11"
              />
              <button
                type="button"
                onClick={() => setShowApiKey((visible) => !visible)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-surface-500 hover:text-surface-200"
                aria-label={showApiKey ? "Hide API key" : "Show API key"}
              >
                {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <div>
            <label htmlFor="chat-model" className="mb-2 block text-sm font-medium text-surface-200">
              Chat model
            </label>
            <select
              id="chat-model"
              value={modelChoice}
              onChange={(event) => setModelChoice(event.target.value)}
              className="input-field"
            >
              {(status?.supported_chat_models || ["gpt-4o-mini", "gpt-4o"]).map((model) => (
                <option key={model} value={model}>{model}</option>
              ))}
              <option value={CUSTOM_MODEL}>Custom model ID</option>
            </select>
            {modelChoice === CUSTOM_MODEL && (
              <input
                type="text"
                value={customModel}
                onChange={(event) => setCustomModel(event.target.value)}
                placeholder="Enter an OpenAI chat-completions model ID"
                className="input-field mt-3"
              />
            )}
            <p className="mt-2 text-xs text-surface-500">
              Embeddings remain on {status?.embedding_model || "text-embedding-3-small"} to keep stored vectors compatible.
            </p>
          </div>

          {!status?.encryption_initialized && (
            <div className="rounded-xl border border-surface-800 bg-surface-950/40">
              <button
                type="button"
                onClick={() => setAdvancedOpen((expanded) => !expanded)}
                className="flex w-full items-center justify-between p-4 text-left text-sm text-surface-300"
                aria-expanded={advancedOpen}
              >
                <span>Advanced encryption options</span>
                <ChevronDown className={`h-4 w-4 transition-transform ${advancedOpen ? "rotate-180" : ""}`} />
              </button>
              {advancedOpen && (
                <div className="space-y-3 border-t border-surface-800 p-4">
                  <label className="flex items-start gap-3 text-sm text-surface-300">
                    <input
                      type="checkbox"
                      checked={useCustomEncryption}
                      onChange={(event) => setUseCustomEncryption(event.target.checked)}
                      className="mt-1"
                    />
                    <span>
                      Provide my own Fernet key. Otherwise CodeLens generates and persists one automatically.
                    </span>
                  </label>
                  {useCustomEncryption && (
                    <input
                      type="password"
                      value={encryptionKey}
                      onChange={(event) => setEncryptionKey(event.target.value)}
                      placeholder="URL-safe base64 Fernet key"
                      autoComplete="new-password"
                      className="input-field"
                    />
                  )}
                </div>
              )}
            </div>
          )}

          {status?.encryption_initialized && (
            <div className="rounded-xl border border-surface-800 bg-surface-950/40 px-4 py-3 text-sm text-surface-400">
              Encryption is initialized and persisted by the backend.
            </div>
          )}

          <div>
            <label htmlFor="admin-password" className="mb-2 block text-sm font-medium text-surface-200">
              CodeLens admin password <span className="text-red-400">*</span>
            </label>
            <input
              id="admin-password"
              type="password"
              value={adminPassword}
              onChange={(event) => setAdminPassword(event.target.value)}
              autoComplete="current-password"
              className="input-field"
            />
          </div>

          {error && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} disabled={saving} className="btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={saving || !status} className="btn-primary flex items-center gap-2">
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {saving ? "Validating..." : "Validate and save"}
            </button>
          </div>
        </form>
        )}
      </div>
    </div>
  );
}
