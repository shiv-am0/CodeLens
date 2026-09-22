const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export class ApiError extends Error {
  status: number;
  code?: string;
  details?: unknown;

  constructor(message: string, status: number, code?: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    const body = await response.text();
    let message = body || `HTTP ${response.status}`;
    let code: string | undefined;
    let details: unknown;

    try {
      const parsed = JSON.parse(body);
      details = parsed.detail;
      if (typeof parsed.detail === "string") {
        message = parsed.detail;
      } else if (parsed.detail && typeof parsed.detail === "object") {
        message = parsed.detail.message || message;
        code = parsed.detail.code;
      }
    } catch {
      // Keep the plain-text response as the error message.
    }

    throw new ApiError(message, response.status, code, details);
  }

  return response.json();
}

export const api = {
  repositories: {
    analyze: (github_url: string) =>
      request<import("@/types").Repository>("/repositories/analyze", {
        method: "POST",
        body: JSON.stringify({ github_url }),
      }),
    reanalyze: (id: number) =>
      request<import("@/types").Repository>(`/repositories/${id}/reanalyze`, {
        method: "POST",
      }),
    get: (id: number) =>
      request<import("@/types").Repository>(`/repositories/${id}`),
    getFiles: (id: number) =>
      request<import("@/types").RepositoryFile[]>(`/repositories/${id}/files`),
    getAnalysis: (id: number) =>
      request<import("@/types").RepositoryAnalysis>(`/repositories/${id}/analysis`),
    getOverview: (id: number) =>
      request<{ overview: string }>(`/repositories/${id}/overview`),
    getArchitecture: (id: number) =>
      request<{ architecture: string }>(`/repositories/${id}/architecture`),
    getFolders: (id: number) =>
      request<{ folder_summary: string }>(`/repositories/${id}/folders`),
    getApi: (id: number) =>
      request<{ api_summary: string }>(`/repositories/${id}/api`),
    getDatabase: (id: number) =>
      request<{ database_summary: string }>(`/repositories/${id}/database`),
    getDiagram: (id: number) =>
      request<{ mermaid_diagram: string }>(`/repositories/${id}/diagram`),
    getReadme: (id: number) =>
      request<{ readme: string }>(`/repositories/${id}/readme`),
    getSuggestions: (id: number) =>
      request<{ suggestions: string }>(`/repositories/${id}/suggestions`),
    chat: (id: number, question: string) =>
      request<{ answer: string }>(`/repositories/${id}/chat`, {
        method: "POST",
        body: JSON.stringify({ question }),
      }),
    getChatHistory: (id: number) =>
      request<import("@/types").ChatMessage[]>(`/repositories/${id}/chat-history`),
  },
};
