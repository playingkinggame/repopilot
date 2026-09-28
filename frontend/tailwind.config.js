export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { bg: "var(--bg)", panel: "var(--panel)", line: "var(--line)", fg: "var(--fg)", mute: "var(--mute)",
                accent: "var(--accent)", ok: "var(--ok)", bad: "var(--bad)", warn: "var(--warn)" },
      fontFamily: { sans: ['"Segoe UI Variable"', '"Segoe UI"', "system-ui", "sans-serif"], mono: ['"Cascadia Code"', "Consolas", "monospace"] },
    },
  },
};
