import axios from "axios";
import {
  IngestResponse,
  QueryRequest,
  QueryResponse,
  ReportResponse,
  DocumentInfo,
} from "../types";

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || "http://localhost:8000",
});

export async function uploadDocument(file: File): Promise<IngestResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post<IngestResponse>("/ingest", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function queryDocuments(
  request: QueryRequest
): Promise<QueryResponse> {
  const { data } = await api.post<QueryResponse>("/query", request);
  return data;
}

export async function generateReport(
  query: string,
  reportType: string = "summary",
  fileFilter?: string
): Promise<ReportResponse> {
  const { data } = await api.post<ReportResponse>("/reports", {
    query,
    report_type: reportType,
    file_filter: fileFilter || null,
  });
  return data;
}

export async function listDocuments(): Promise<DocumentInfo[]> {
  const { data } = await api.get<{ documents: DocumentInfo[] }>("/documents");
  return data.documents;
}

export async function deleteDocument(documentId: string): Promise<void> {
  await api.delete(`/documents/${documentId}`);
}

export interface AnalyzeResponse {
  total_rows: number;
  categories: Record<string, number>;
  top_entities: { category: string; entity: string; mentions: number }[];
  linux_tickets: { row: number; text: string }[];
}

export async function analyzeDataset(): Promise<AnalyzeResponse> {
  const { data } = await api.get<AnalyzeResponse>("/analyze");
  return data;
}
