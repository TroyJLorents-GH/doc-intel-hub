import React, { useState, useCallback } from "react";
import {
  Box,
  Card,
  CardContent,
  Typography,
  LinearProgress,
  Alert,
  Chip,
  Stack,
  useTheme,
} from "@mui/material";
import {
  CloudUpload as UploadIcon,
  CheckCircle as SuccessIcon,
  Description as FileIcon,
} from "@mui/icons-material";
import { useDropzone } from "react-dropzone";
import { uploadDocument } from "../services/api";
import { IngestResponse } from "../types";

const ACCEPTED_TYPES: Record<string, string[]> = {
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
  "text/csv": [".csv"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "application/json": [".json"],
  "image/jpeg": [".jpg", ".jpeg"],
  "image/png": [".png"],
  "image/tiff": [".tiff"],
};

export default function UploadPanel() {
  const theme = useTheme();
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState<IngestResponse[]>([]);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    setError(null);
    for (const file of acceptedFiles) {
      setUploading(true);
      try {
        const result = await uploadDocument(file);
        setResults((prev) => [result, ...prev]);
      } catch (err: any) {
        setError(err.response?.data?.detail || `Failed to upload ${file.name}`);
      } finally {
        setUploading(false);
      }
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: 50 * 1024 * 1024,
  });

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Upload Documents
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Upload files to ingest into the knowledge base. Supports PDF, DOCX, CSV, XLSX, JSON, and images.
      </Typography>

      {/* Dropzone */}
      <Card
        {...getRootProps()}
        sx={{
          cursor: "pointer",
          border: `2px dashed ${isDragActive ? theme.palette.primary.main : theme.palette.divider}`,
          bgcolor: isDragActive ? "rgba(108, 99, 255, 0.05)" : "transparent",
          transition: "all 0.2s",
          "&:hover": {
            borderColor: theme.palette.primary.main,
            bgcolor: "rgba(108, 99, 255, 0.03)",
          },
        }}
      >
        <CardContent
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            py: 6,
          }}
        >
          <input {...getInputProps()} />
          <UploadIcon sx={{ fontSize: 56, color: "primary.main", mb: 2, opacity: 0.8 }} />
          <Typography variant="h6" gutterBottom>
            {isDragActive ? "Drop files here" : "Drag & drop files here"}
          </Typography>
          <Typography color="text.secondary" sx={{ mb: 2 }}>
            or click to browse
          </Typography>
          <Stack direction="row" spacing={0.5} flexWrap="wrap" justifyContent="center" useFlexGap>
            {["PDF", "DOCX", "CSV", "XLSX", "JSON", "JPEG", "PNG"].map((type) => (
              <Chip key={type} label={type} size="small" variant="outlined" />
            ))}
          </Stack>
        </CardContent>
      </Card>

      {uploading && (
        <Box sx={{ mt: 2 }}>
          <LinearProgress sx={{ borderRadius: 1 }} />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Processing document... Extracting text, generating embeddings, and building graph...
          </Typography>
        </Box>
      )}

      {error && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {error}
        </Alert>
      )}

      {/* Results */}
      {results.length > 0 && (
        <Box sx={{ mt: 3 }}>
          <Typography variant="h6" gutterBottom>
            Ingested Documents
          </Typography>
          <Stack spacing={1.5}>
            {results.map((r) => (
              <Card key={r.document_id} sx={{ bgcolor: "rgba(16, 185, 129, 0.05)" }}>
                <CardContent sx={{ display: "flex", alignItems: "center", gap: 2, py: 1.5, "&:last-child": { pb: 1.5 } }}>
                  <SuccessIcon color="success" />
                  <FileIcon sx={{ color: "text.secondary" }} />
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="body1" fontWeight={600}>
                      {r.file_name}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {r.total_chunks} chunks, {r.entities_extracted} entities
                    </Typography>
                  </Box>
                  <Chip label={r.file_type.toUpperCase()} size="small" color="primary" variant="outlined" />
                </CardContent>
              </Card>
            ))}
          </Stack>
        </Box>
      )}
    </Box>
  );
}
