import React, { useState } from "react";
import { ThemeProvider, CssBaseline } from "@mui/material";
import { LicenseInfo } from "@mui/x-license";
import theme from "./theme";
import Layout from "./components/Layout";
import UploadPanel from "./components/UploadPanel";
import ChatPanel from "./components/ChatPanel";
import ReportsPanel from "./components/ReportsPanel";
import DocumentsPanel from "./components/DocumentsPanel";

// MUI X Pro License
const licenseKey = process.env.REACT_APP_MUI_LICENSE_KEY;
if (licenseKey) {
  LicenseInfo.setLicenseKey(licenseKey);
}

function App() {
  const [activeTab, setActiveTab] = useState("upload");

  const renderPanel = () => {
    switch (activeTab) {
      case "upload":
        return <UploadPanel />;
      case "chat":
        return <ChatPanel />;
      case "reports":
        return <ReportsPanel />;
      case "documents":
        return <DocumentsPanel />;
      default:
        return <UploadPanel />;
    }
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Layout activeTab={activeTab} onTabChange={setActiveTab}>
        {renderPanel()}
      </Layout>
    </ThemeProvider>
  );
}

export default App;
