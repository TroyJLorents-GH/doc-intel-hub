import React, { useState, useRef, useEffect } from "react";
import {
  Box,
  Card,
  CardContent,
  IconButton,
  TextField,
  Typography,
  Chip,
  Collapse,
  Stack,
  CircularProgress,
  useTheme,
  FormControlLabel,
  Switch,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from "@mui/material";
import {
  Send as SendIcon,
  ExpandMore as ExpandIcon,
  Source as SourceIcon,
} from "@mui/icons-material";
import ReactMarkdown from "react-markdown";
import { queryDocuments } from "../services/api";
import { QueryResponse } from "../types";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: QueryResponse["sources"];
  queriesUsed?: string[];
}

export default function ChatPanel() {
  const theme = useTheme();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [useMultiQuery, setUseMultiQuery] = useState(true);
  const [useExpansion, setUseExpansion] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMsg: ChatMessage = { role: "user", content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const response = await queryDocuments({
        query: input,
        use_multi_query: useMultiQuery,
        use_query_expansion: useExpansion,
        top_k: 10,
      });

      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: response.answer,
        sources: response.sources,
        queriesUsed: response.queries_used,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error: " + (err.response?.data?.detail || err.message) },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "calc(100vh - 48px)" }}>
      <Typography variant="h4" gutterBottom>
        Ask Your Data
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        Chat with your ingested documents using Agentic RAG.
      </Typography>

      {/* Settings */}
      <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
        <FormControlLabel
          control={<Switch checked={useMultiQuery} onChange={(e) => setUseMultiQuery(e.target.checked)} size="small" />}
          label={<Typography variant="body2">Multi-Query RAG</Typography>}
        />
        <FormControlLabel
          control={<Switch checked={useExpansion} onChange={(e) => setUseExpansion(e.target.checked)} size="small" />}
          label={<Typography variant="body2">Query Expansion</Typography>}
        />
      </Stack>

      {/* Messages */}
      <Box sx={{ flex: 1, overflow: "auto", mb: 2 }}>
        {messages.length === 0 && (
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", opacity: 0.5 }}>
            <Typography color="text.secondary">
              Upload documents, then ask questions about your data.
            </Typography>
          </Box>
        )}
        <Stack spacing={2}>
          {messages.map((msg, i) => (
            <Box
              key={i}
              sx={{
                display: "flex",
                justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
              }}
            >
              <Card
                sx={{
                  maxWidth: "80%",
                  bgcolor:
                    msg.role === "user"
                      ? "rgba(108, 99, 255, 0.15)"
                      : "background.paper",
                }}
              >
                <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
                  <Box sx={{ "& p": { m: 0 }, "& pre": { bgcolor: "rgba(0,0,0,0.3)", p: 1.5, borderRadius: 1, overflow: "auto" } }}>
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </Box>

                  {/* Sources accordion */}
                  {msg.sources && msg.sources.length > 0 && (
                    <Accordion
                      disableGutters
                      elevation={0}
                      sx={{ mt: 1, bgcolor: "transparent", "&:before": { display: "none" } }}
                    >
                      <AccordionSummary expandIcon={<ExpandIcon />} sx={{ px: 0, minHeight: "auto" }}>
                        <Stack direction="row" spacing={1} alignItems="center">
                          <SourceIcon fontSize="small" color="secondary" />
                          <Typography variant="body2" color="secondary">
                            {msg.sources.length} sources
                          </Typography>
                        </Stack>
                      </AccordionSummary>
                      <AccordionDetails sx={{ px: 0 }}>
                        <Stack spacing={1}>
                          {msg.sources.slice(0, 5).map((s, j) => (
                            <Box key={j} sx={{ p: 1, bgcolor: "rgba(0,0,0,0.2)", borderRadius: 1 }}>
                              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
                                <Chip label={s.source_file} size="small" variant="outlined" />
                                <Chip label={`Score: ${s.score.toFixed(3)}`} size="small" color="secondary" />
                              </Stack>
                              <Typography variant="body2" color="text.secondary" sx={{ fontSize: "0.8rem" }}>
                                {s.text.slice(0, 200)}...
                              </Typography>
                            </Box>
                          ))}
                        </Stack>

                        {/* Queries used */}
                        {msg.queriesUsed && (
                          <Box sx={{ mt: 1.5 }}>
                            <Typography variant="caption" color="text.secondary">
                              Queries used:
                            </Typography>
                            <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
                              {msg.queriesUsed.map((q, k) => (
                                <Chip key={k} label={q} size="small" variant="outlined" sx={{ fontSize: "0.7rem" }} />
                              ))}
                            </Stack>
                          </Box>
                        )}
                      </AccordionDetails>
                    </Accordion>
                  )}
                </CardContent>
              </Card>
            </Box>
          ))}
          {loading && (
            <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
              <CircularProgress size={20} />
              <Typography variant="body2" color="text.secondary">
                Searching and analyzing...
              </Typography>
            </Box>
          )}
          <div ref={scrollRef} />
        </Stack>
      </Box>

      {/* Input */}
      <Box sx={{ display: "flex", gap: 1 }}>
        <TextField
          fullWidth
          placeholder="Ask about your documents..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
          multiline
          maxRows={3}
          size="small"
          sx={{
            "& .MuiOutlinedInput-root": {
              bgcolor: "background.paper",
            },
          }}
        />
        <IconButton
          onClick={handleSend}
          disabled={loading || !input.trim()}
          sx={{
            bgcolor: "primary.main",
            color: "white",
            "&:hover": { bgcolor: "primary.dark" },
            "&:disabled": { bgcolor: "action.disabledBackground" },
          }}
        >
          <SendIcon />
        </IconButton>
      </Box>
    </Box>
  );
}
