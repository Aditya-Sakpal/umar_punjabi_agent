import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { WarRoom } from "./pages/WarRoom";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <WarRoom />
  </StrictMode>,
);
