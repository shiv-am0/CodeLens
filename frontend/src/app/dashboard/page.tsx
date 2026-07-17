"use client";
import { useEffect, useState, Suspense, useRef } from "react";
import { useSearchParams } from "next/navigation";
import Sidebar from "@/components/layout/Sidebar";
import AnalysisContent from "@/components/dashboard/AnalysisContent";
import MermaidDiagram from "@/components/dashboard/MermaidDiagram";
import ChatInterface from "@/components/chat/ChatInterface";
import { api } from "@/services/api";
import { getStatusColor } from "@/lib/utils";
import { Clock, FileCode, GitBranch, Globe } from "lucide-react";

function DashboardContent() {
  const searchParams = useSearchParams();
  const repoId = searchParams.get("id") || "";
  const section = searchParams.get("section") || "overview";

  const [repo, setRepo] = useState<any>(null);
  const [analysis, setAnalysis] = useState<any>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const retryCountRef = useRef(0);
  const MAX_RETRIES = 120;

  const stopPolling = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  const loadData = async () => {
    try {
      const repoData = await api.repositories.get(Number(repoId));
      setRepo(repoData);
      if (repoData.status === "completed") {
        const analysisData = await api.repositories.getAnalysis(Number(repoId));
        setAnalysis(analysisData);
        setLoading(false);
        stopPolling();
      } else if (repoData.status === "failed") {
        setError("Analysis failed. Please try again.");
        setLoading(false);
        stopPolling();
      } else {
        retryCountRef.current += 1;
        if (retryCountRef.current >= MAX_RETRIES) {
          setError("Analysis timed out. Please try again.");
          setLoading(false);
          stopPolling();
        }
      }
    } catch (err: any) {
      setError(err.message);
      setLoading(false);
      stopPolling();
    }
  };

  useEffect(() => {
    if (!repoId) return;
    retryCountRef.current = 0;
    loadData();
    intervalRef.current = setInterval(loadData, 5000);
    return () => {
      stopPolling();
    };
  }, [repoId]);

  const renderContent = () => {
    if (!repoId) {
      return (
        <div className="flex items-center justify-center h-full">
          <p className="text-surface-500">No repository selected.</p>
        </div>
      );
    }

    if (error) {
      return (
        <div className="flex items-center justify-center h-full">
          <div className="text-center">
            <p className="text-red-400 mb-2">Error: {error}</p>
            <button onClick={loadData} className="btn-secondary text-sm">
              Retry
            </button>
          </div>
        </div>
      );
    }

    if (!repo || repo.status !== "completed") {
      const statusLabels: Record<string, string> = {
        pending: "Queued...",
        cloning: "Cloning repository...",
        indexing: "Indexing files...",
        embedding: "Generating embeddings...",
        analyzing: "Running AI analysis...",
      };
      return (
        <div className="flex items-center justify-center h-full">
          <div className="text-center max-w-md">
            <div className="w-12 h-12 border-2 border-accent/30 border-t-accent rounded-full animate-spin mx-auto mb-6" />
            <h3 className="text-lg font-semibold text-surface-100 mb-2">
              Analyzing Repository
            </h3>
            <p className="text-surface-400 mb-4">
              {statusLabels[repo?.status] || "Processing..."}
            </p>
            {repo?.status && (
              <div className="flex items-center justify-center gap-2 text-sm text-surface-500">
                <div className={`w-2 h-2 rounded-full ${getStatusColor(repo.status)}`} />
                <span className="capitalize">{repo.status}</span>
              </div>
            )}
          </div>
        </div>
      );
    }

    switch (section) {
      case "overview":
        return (
          <AnalysisContent
            content={analysis?.overview}
            isLoading={loading}
            emptyMessage="Overview not available."
          />
        );
      case "architecture":
        return (
          <AnalysisContent
            content={analysis?.architecture}
            isLoading={loading}
            emptyMessage="Architecture explanation not available."
          />
        );
      case "folders":
        return (
          <AnalysisContent
            content={analysis?.folder_summary}
            isLoading={loading}
            emptyMessage="Folder summary not available."
          />
        );
      case "api":
        return (
          <AnalysisContent
            content={analysis?.api_summary}
            isLoading={loading}
            emptyMessage="API documentation not available."
          />
        );
      case "database":
        return (
          <AnalysisContent
            content={analysis?.database_summary}
            isLoading={loading}
            emptyMessage="Database analysis not available."
          />
        );
      case "diagram":
        return (
          <div className="h-[calc(100vh-12rem)]">
            <h2 className="text-2xl font-bold text-surface-100 mb-6">Architecture Diagram</h2>
            <div className="h-[calc(100%-3rem)]">
              <MermaidDiagram chart={analysis?.mermaid_diagram || ""} />
            </div>
          </div>
        );
      case "readme":
        return (
          <AnalysisContent
            content={analysis?.readme}
            isLoading={loading}
            emptyMessage="README not available."
          />
        );
      case "suggestions":
        return (
          <AnalysisContent
            content={analysis?.suggestions}
            isLoading={loading}
            emptyMessage="Suggestions not available."
          />
        );
      case "chat":
        return <ChatInterface repoId={Number(repoId)} />;
      default:
        return (
          <AnalysisContent
            content={analysis?.overview}
            isLoading={loading}
            emptyMessage="Analysis not available."
          />
        );
    }
  };

  if (!repoId) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-surface-100 mb-4">No Repository Selected</h2>
          <p className="text-surface-400 mb-6">Go back to the homepage and enter a GitHub URL.</p>
          <a href="/" className="btn-primary">Go Home</a>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen">
      <Sidebar repoId={repoId} />
      <main className="flex-1 overflow-y-auto">
        {section !== "chat" && repo?.status === "completed" && (
          <div className="p-6 border-b border-surface-800/50">
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-2xl font-bold text-surface-100 capitalize mb-1">
                  {section.replace("_", " ")}
                </h1>
                <div className="flex items-center gap-4 text-sm text-surface-400">
                  <span className="flex items-center gap-1">
                    <GitBranch className="w-3.5 h-3.5" />
                    {repo.owner}/{repo.repo_name}
                  </span>
                  <span className="flex items-center gap-1">
                    <Globe className="w-3.5 h-3.5" />
                    {repo.language || "Unknown"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
        <div className={section === "chat" ? "" : "p-6"}>
          {renderContent()}
        </div>
      </main>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    }>
      <DashboardContent />
    </Suspense>
  );
}
