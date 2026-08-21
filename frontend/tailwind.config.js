/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Muted SOC-style palette — deliberately low-saturation so
        // alert severity colors (used sparingly) stand out.
        vexus: {
          bg: "#0b0f14",
          panel: "#121822",
          border: "#1f2937",
          text: "#e5e7eb",
          muted: "#9ca3af",
          accent: "#3b82f6",
        },
      },
    },
  },
  plugins: [],
};
