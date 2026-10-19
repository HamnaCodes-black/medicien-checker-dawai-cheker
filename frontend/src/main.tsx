import "@fontsource-variable/inter";
import "@fontsource-variable/noto-sans-arabic";
import "@fontsource/noto-nastaliq-urdu/400.css";
import "./index.css";
import "./i18n";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AppProvider } from "./context/AppContext";
import { ToastProvider } from "./context/ToastContext";
import { applyTheme, initialTheme } from "./lib/theme";

applyTheme(initialTheme());

const root = document.getElementById("root");
if (!root) throw new Error("Root element not found");

createRoot(root).render(
  <StrictMode>
    <BrowserRouter>
      <AppProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </AppProvider>
    </BrowserRouter>
  </StrictMode>,
);
