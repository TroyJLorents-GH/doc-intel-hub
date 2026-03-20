import React, { useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
  CircularProgress,
  useTheme,
} from "@mui/material";
import { Assessment as ReportIcon } from "@mui/icons-material";
import { BarChart, PieChart } from "@mui/x-charts";
import ReactMarkdown from "react-markdown";
import { generateReport } from "../services/api";
import { ReportResponse } from "../types";

export default function ReportsPanel() {
  const theme = useTheme();
  const [query, setQuery] = useState("");
  const [reportType, setReportType] = useState("categorization");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const result = await generateReport(query, reportType);
      setReport(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Generate Reports
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Analyze your data and generate structured reports with charts and breakdowns.
      </Typography>

      {/* Controls */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Stack spacing={2}>
            <TextField
              fullWidth
              label="What do you want to analyze?"
              placeholder='e.g., "Categorize ServiceNow tickets by issue type and count how many are Linux-related"'
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              multiline
              rows={2}
            />
            <Stack direction="row" spacing={2} alignItems="center">
              <FormControl sx={{ minWidth: 200 }}>
                <InputLabel>Report Type</InputLabel>
                <Select
                  value={reportType}
                  label="Report Type"
                  onChange={(e) => setReportType(e.target.value)}
                >
                  <MenuItem value="summary">Summary</MenuItem>
                  <MenuItem value="categorization">Categorization</MenuItem>
                  <MenuItem value="trend">Trend Analysis</MenuItem>
                  <MenuItem value="comparison">Comparison</MenuItem>
                </Select>
              </FormControl>
              <Button
                variant="contained"
                size="large"
                startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <ReportIcon />}
                onClick={handleGenerate}
                disabled={loading || !query.trim()}
              >
                {loading ? "Generating..." : "Generate Report"}
              </Button>
            </Stack>
          </Stack>
        </CardContent>
      </Card>

      {error && (
        <Card sx={{ mb: 2, bgcolor: "rgba(239, 68, 68, 0.1)" }}>
          <CardContent>
            <Typography color="error">{error}</Typography>
          </CardContent>
        </Card>
      )}

      {/* Report Output */}
      {report && (
        <Box>
          <Card sx={{ mb: 3, border: `1px solid ${theme.palette.primary.dark}` }}>
            <CardContent>
              <Typography variant="h5" gutterBottom>
                {report.title}
              </Typography>
              <Typography color="text.secondary" sx={{ mb: 1 }}>
                {report.summary}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Analyzed {report.total_documents_analyzed} document chunks
              </Typography>
            </CardContent>
          </Card>

          <Stack spacing={3}>
            {report.sections.map((section, i) => (
              <Card key={i}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    {section.title}
                  </Typography>

                  <Box sx={{ "& p": { mt: 0 }, "& ul": { pl: 2 } }}>
                    <ReactMarkdown>{section.content}</ReactMarkdown>
                  </Box>

                  {/* Chart */}
                  {section.chart_data && (
                    <Box sx={{ mt: 2, height: 300 }}>
                      {section.chart_data.type === "pie" ? (
                        <PieChart
                          series={[
                            {
                              data: section.chart_data.labels.map((label, j) => ({
                                id: j,
                                value: section.chart_data!.values[j],
                                label,
                              })),
                              highlightScope: { fade: "global", highlight: "item" },
                            },
                          ]}
                          height={280}
                        />
                      ) : (
                        <BarChart
                          xAxis={[{ scaleType: "band", data: section.chart_data.labels }]}
                          series={[
                            {
                              data: section.chart_data.values,
                              label: section.chart_data.label,
                              color: theme.palette.primary.main,
                            },
                          ]}
                          height={280}
                        />
                      )}
                    </Box>
                  )}

                  {/* Table */}
                  {section.table_data && section.table_data.length > 0 && (
                    <Box sx={{ mt: 2, overflow: "auto" }}>
                      <table style={{ width: "100%", borderCollapse: "collapse" }}>
                        <thead>
                          <tr>
                            {Object.keys(section.table_data[0]).map((col) => (
                              <th
                                key={col}
                                style={{
                                  textAlign: "left",
                                  padding: "8px 12px",
                                  borderBottom: `2px solid ${theme.palette.divider}`,
                                  color: theme.palette.text.secondary,
                                  fontSize: "0.85rem",
                                  fontWeight: 600,
                                }}
                              >
                                {col}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {section.table_data.map((row, j) => (
                            <tr key={j}>
                              {Object.values(row).map((val, k) => (
                                <td
                                  key={k}
                                  style={{
                                    padding: "8px 12px",
                                    borderBottom: `1px solid ${theme.palette.divider}`,
                                    fontSize: "0.85rem",
                                    color: theme.palette.text.primary,
                                  }}
                                >
                                  {val}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </Box>
                  )}
                </CardContent>
              </Card>
            ))}
          </Stack>
        </Box>
      )}
    </Box>
  );
}
