import React from "react";
import {
  AppBar,
  Box,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  useTheme,
} from "@mui/material";
import {
  CloudUpload as UploadIcon,
  Chat as ChatIcon,
  Assessment as ReportIcon,
  Description as DocsIcon,
  Hub as HubIcon,
  Menu as MenuIcon,
} from "@mui/icons-material";

const DRAWER_WIDTH = 260;

interface LayoutProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  children: React.ReactNode;
}

const tabs = [
  { id: "upload", label: "Upload Documents", icon: <UploadIcon /> },
  { id: "chat", label: "Ask Your Data", icon: <ChatIcon /> },
  { id: "reports", label: "Generate Reports", icon: <ReportIcon /> },
  { id: "documents", label: "Documents", icon: <DocsIcon /> },
];

export default function Layout({ activeTab, onTabChange, children }: LayoutProps) {
  const theme = useTheme();
  const [mobileOpen, setMobileOpen] = React.useState(false);

  const drawer = (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <Box
        sx={{
          p: 2.5,
          display: "flex",
          alignItems: "center",
          gap: 1.5,
          borderBottom: `1px solid ${theme.palette.divider}`,
        }}
      >
        <HubIcon sx={{ color: theme.palette.primary.main, fontSize: 32 }} />
        <Box>
          <Typography variant="h6" sx={{ fontSize: "1.1rem", lineHeight: 1.2 }}>
            Doc Intel Hub
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Agentic RAG Platform
          </Typography>
        </Box>
      </Box>
      <List sx={{ px: 1.5, pt: 2, flex: 1 }}>
        {tabs.map((tab) => (
          <ListItemButton
            key={tab.id}
            selected={activeTab === tab.id}
            onClick={() => {
              onTabChange(tab.id);
              setMobileOpen(false);
            }}
            sx={{
              borderRadius: 2,
              mb: 0.5,
              "&.Mui-selected": {
                bgcolor: "rgba(108, 99, 255, 0.15)",
                "&:hover": { bgcolor: "rgba(108, 99, 255, 0.2)" },
                "& .MuiListItemIcon-root": { color: theme.palette.primary.main },
              },
            }}
          >
            <ListItemIcon sx={{ minWidth: 40 }}>{tab.icon}</ListItemIcon>
            <ListItemText
              primary={tab.label}
              primaryTypographyProps={{ fontSize: "0.9rem", fontWeight: 500 }}
            />
          </ListItemButton>
        ))}
      </List>
    </Box>
  );

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "background.default" }}>
      {/* Mobile app bar */}
      <AppBar
        position="fixed"
        sx={{
          display: { md: "none" },
          bgcolor: "background.paper",
          borderBottom: `1px solid ${theme.palette.divider}`,
        }}
        elevation={0}
      >
        <Toolbar>
          <IconButton edge="start" onClick={() => setMobileOpen(!mobileOpen)}>
            <MenuIcon />
          </IconButton>
          <Typography variant="h6">Doc Intel Hub</Typography>
        </Toolbar>
      </AppBar>

      {/* Sidebar */}
      <Box component="nav" sx={{ width: { md: DRAWER_WIDTH }, flexShrink: 0 }}>
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          sx={{
            display: { xs: "block", md: "none" },
            "& .MuiDrawer-paper": {
              width: DRAWER_WIDTH,
              bgcolor: "background.paper",
              borderRight: `1px solid ${theme.palette.divider}`,
            },
          }}
        >
          {drawer}
        </Drawer>
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: "none", md: "block" },
            "& .MuiDrawer-paper": {
              width: DRAWER_WIDTH,
              bgcolor: "background.paper",
              borderRight: `1px solid ${theme.palette.divider}`,
            },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>

      {/* Main content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          mt: { xs: 8, md: 0 },
          maxWidth: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
        }}
      >
        {children}
      </Box>
    </Box>
  );
}
