export interface IngestResponse {
  document_id: string;
  file_name: string;
  file_type: string;
  total_chunks: number;
  entities_extracted: number;
  message: string;
}

export interface QueryRequest {
  query: string;
  use_multi_query?: boolean;
  use_query_expansion?: boolean;
  top_k?: number;
  file_filter?: string | null;
}

export interface QueryResult {
  chunk_id: string;
  text: string;
  score: number;
  source_file: string;
  section_type?: string;
  heading_path?: string[];
  contextual_prefix?: string;
}

export interface QueryResponse {
  answer: string;
  sources: QueryResult[];
  queries_used: string[];
}

export interface ReportSection {
  title: string;
  content: string;
  chart_data?: {
    type: "bar" | "pie" | "line";
    labels: string[];
    values: number[];
    label: string;
  } | null;
  table_data?: Record<string, string>[] | null;
}

export interface ReportResponse {
  title: string;
  summary: string;
  sections: ReportSection[];
  total_documents_analyzed: number;
}

export interface DocumentInfo {
  id: string;
  filename: string;
  ingested_at: string;
  chunk_count: number;
}
