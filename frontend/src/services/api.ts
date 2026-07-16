const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
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
  });

  if (!response.ok) {
    const error = await response.text();
    throw new ApiError(error || `HTTP ${response.status}`, response.status);
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
