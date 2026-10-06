import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// GitHub Pages serves under /spot-watchlist/
export default defineConfig({
  plugins: [react()],
  base: "/spot-watchlist/",
});
