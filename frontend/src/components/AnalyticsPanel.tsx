import React, { useEffect, useState } from "react";
import {
  Box,
  Card,
  CardContent,
  CircularProgress,
  IconButton,
  Stack,
  Typography,
  Chip,
  useTheme,
} from "@mui/material";
import {
  Refresh as RefreshIcon,
} from "@mui/icons-material";
import { BarChart, PieChart } from "@mui/x-charts";
import { analyzeDataset, AnalyzeResponse } from "../services/api";

export default function AnalyticsPanel() {
  const theme = useTheme();
  const [data, setData] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const result = await analyzeDataset();
      setData(result);
    } catch {
      // API error
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 10 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!data) {
    return (
      <Card>
        <CardContent sx={{ textAlign: "center", py: 6 }}>
          <Typography color="text.secondary">
            No data available. Upload and ingest documents first.
          </Typography>
        </CardContent>
      </Card>
    );
  }

  // Prepare category chart data — sort by count descending
  const categoryEntries = Object.entries(data.categories)
    .sort((a, b) => b[1] - a[1]);
  const categoryLabels = categoryEntries.map(([k]) =>
    k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  );
  const categoryValues = categoryEntries.map(([, v]) => v);

  // Top entities for pie chart
  const entitySlices = data.top_entities.slice(0, 10).map((e, i) => ({
    id: i,
    value: e.mentions,
    label: `${e.entity} (${e.category})`,
  }));

  return (
    <Box>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 3 }}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Dataset Analytics
          </Typography>
          <Typography color="text.secondary">
            Full scan of all {data.total_rows.toLocaleString()} rows in Neo4j
          </Typography>
        </Box>
        <IconButton onClick={fetchData}>
          <RefreshIcon />
        </IconButton>
      </Stack>

      {/* Summary Cards */}
      <Stack direction="row" spacing={2} sx={{ mb: 3 }} flexWrap="wrap" useFlexGap>
        <Card sx={{ flex: 1, minWidth: 150 }}>
          <CardContent sx={{ textAlign: "center" }}>
            <Typography variant="h3" color="primary.main" fontWeight={700}>
              {data.total_rows.toLocaleString()}
            </Typography>
            <Typography color="text.secondary">Total Rows</Typography>
          </CardContent>
        </Card>
        <Card sx={{ flex: 1, minWidth: 150 }}>
          <CardContent sx={{ textAlign: "center" }}>
            <Typography variant="h3" color="secondary.main" fontWeight={700}>
              {Object.keys(data.categories).length}
            </Typography>
            <Typography color="text.secondary">Categories Found</Typography>
          </CardContent>
        </Card>
        <Card sx={{ flex: 1, minWidth: 150 }}>
          <CardContent sx={{ textAlign: "center" }}>
            <Typography variant="h3" color="success.main" fontWeight={700}>
              {data.categories.linux || 0}
            </Typography>
            <Typography color="text.secondary">Linux Tickets</Typography>
          </CardContent>
        </Card>
        <Card sx={{ flex: 1, minWidth: 150 }}>
          <CardContent sx={{ textAlign: "center" }}>
            <Typography variant="h3" color="warning.main" fontWeight={700}>
              {data.top_entities.length}
            </Typography>
            <Typography color="text.secondary">Top Entities</Typography>
          </CardContent>
        </Card>
      </Stack>

      {/* Category Breakdown */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Ticket Categories (Keyword Count Across All Rows)
          </Typography>
          {categoryEntries.length > 0 && (
            <Box sx={{ height: 400 }}>
              <BarChart
                xAxis={[{
                  scaleType: "band",
                  data: categoryLabels,
                  tickLabelStyle: { angle: -35, textAnchor: "end", fontSize: 11 },
                }]}
                series={[{
                  data: categoryValues,
                  label: "Ticket Count",
                  color: theme.palette.primary.main,
                }]}
                height={380}
                margin={{ bottom: 100 }}
              />
            </Box>
          )}
          {/* Raw numbers */}
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 2 }}>
            {categoryEntries.map(([key, val]) => (
              <Chip
                key={key}
                label={`${key.replace(/_/g, " ")}: ${val}`}
                color={key === "linux" ? "success" : "default"}
                variant={key === "linux" ? "filled" : "outlined"}
              />
            ))}
          </Stack>
        </CardContent>
      </Card>

      {/* Top Entities */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Most Mentioned Entities
          </Typography>
          {entitySlices.length > 0 ? (
            <Box sx={{ height: 350 }}>
              <PieChart
                series={[{
                  data: entitySlices,
                  highlightScope: { fade: "global", highlight: "item" },
                  innerRadius: 40,
                }]}
                height={330}
              />
            </Box>
          ) : (
            <Typography color="text.secondary">No entities extracted yet.</Typography>
          )}
          {/* Entity table */}
          <Box sx={{ mt: 2, maxHeight: 300, overflow: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Entity", "Category", "Mentions"].map((col) => (
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
                {data.top_entities.map((e, i) => (
                  <tr key={i}>
                    <td style={{ padding: "6px 12px", borderBottom: `1px solid ${theme.palette.divider}`, fontSize: "0.85rem" }}>
                      {e.entity}
                    </td>
                    <td style={{ padding: "6px 12px", borderBottom: `1px solid ${theme.palette.divider}`, fontSize: "0.85rem" }}>
                      <Chip label={e.category} size="small" variant="outlined" />
                    </td>
                    <td style={{ padding: "6px 12px", borderBottom: `1px solid ${theme.palette.divider}`, fontSize: "0.85rem" }}>
                      {e.mentions}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Box>
        </CardContent>
      </Card>

      {/* Print-friendly summary */}
      <Card sx={{ "@media print": { breakInside: "avoid" } }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Dataset Summary
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Total Rows: {data.total_rows.toLocaleString()} |
            Categories Detected: {Object.keys(data.categories).length} |
            Top Category: {categoryEntries[0]?.[0]?.replace(/_/g, " ")} ({categoryEntries[0]?.[1]}) |
            Entities Tracked: {data.top_entities.length}
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
}
