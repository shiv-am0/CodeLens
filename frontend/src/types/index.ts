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

export interface AIConfigurationStatus {
  provider: string;
  configured: boolean;
  api_key_configured: boolean;
  chat_model: string;
  embedding_model: string;
  encryption_initialized: boolean;
  supported_chat_models: string[];
}

export interface AIConfigurationUpdate {
  admin_password: string;
  api_key?: string;
  chat_model: string;
  encryption_key?: string;
}
