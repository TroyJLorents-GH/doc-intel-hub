import React, { useEffect, useState } from "react";
import {
  Box,
  Card,
  CardContent,
  IconButton,
  Stack,
  Typography,
  Chip,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
} from "@mui/material";
import {
  Delete as DeleteIcon,
  Refresh as RefreshIcon,
  Description as FileIcon,
} from "@mui/icons-material";
import { listDocuments, deleteDocument } from "../services/api";
import { DocumentInfo } from "../types";

export default function DocumentsPanel() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<DocumentInfo | null>(null);

  const fetchDocs = async () => {
    setLoading(true);
    try {
      const docs = await listDocuments();
      setDocuments(docs);
    } catch {
      // API not connected
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteDocument(deleteTarget.id);
      setDocuments((prev) => prev.filter((d) => d.id !== deleteTarget.id));
    } catch {
      // Handle error
    }
    setDeleteTarget(null);
  };

  return (
    <Box>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 3 }}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Documents
          </Typography>
          <Typography color="text.secondary">
            {documents.length} documents ingested
          </Typography>
        </Box>
        <IconButton onClick={fetchDocs} disabled={loading}>
          <RefreshIcon />
        </IconButton>
      </Stack>

      {loading ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      ) : documents.length === 0 ? (
        <Card>
          <CardContent sx={{ textAlign: "center", py: 6 }}>
            <FileIcon sx={{ fontSize: 48, color: "text.secondary", mb: 2, opacity: 0.5 }} />
            <Typography color="text.secondary">
              No documents ingested yet. Upload files to get started.
            </Typography>
          </CardContent>
        </Card>
      ) : (
        <Stack spacing={1.5}>
          {documents.map((doc) => (
            <Card key={doc.id}>
              <CardContent
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 2,
                  py: 1.5,
                  "&:last-child": { pb: 1.5 },
                }}
              >
                <FileIcon sx={{ color: "primary.main" }} />
                <Box sx={{ flex: 1 }}>
                  <Typography fontWeight={600}>{doc.filename}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {doc.chunk_count} chunks
                    {doc.ingested_at && ` \u2022 ${new Date(doc.ingested_at).toLocaleString()}`}
                  </Typography>
                </Box>
                <Chip
                  label={`${doc.chunk_count} chunks`}
                  size="small"
                  color="secondary"
                  variant="outlined"
                />
                <IconButton
                  size="small"
                  onClick={() => setDeleteTarget(doc)}
                  sx={{ color: "error.main" }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}

      {/* Delete confirmation */}
      <Dialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)}>
        <DialogTitle>Delete Document</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Delete <strong>{deleteTarget?.filename}</strong> and all its chunks? This cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteTarget(null)}>Cancel</Button>
          <Button onClick={handleDelete} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
