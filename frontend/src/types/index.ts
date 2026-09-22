export interface Repository {
  id: number;
  github_url: string;
  owner: string;
  repo_name: string;
  branch: string;
  language: string | null;
  status: string;
  created_at: string;
}

export interface RepositoryFile {
  id: number;
  path: string;
  size: number;
}

export interface RepositoryAnalysis {
  overview: string | null;
  architecture: string | null;
  folder_summary: string | null;
  api_summary: string | null;
  database_summary: string | null;
  mermaid_diagram: string | null;
  readme: string | null;
  suggestions: string | null;
}

export interface ChatMessage {
  id: number;
  question: string;
  answer: string;
  timestamp: string;
}
