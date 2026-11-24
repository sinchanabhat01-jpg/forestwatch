export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        canopy: { 950: "#050b07", 900: "#0a1a10", 800: "#0f2a1a", 700: "#14402a", 600: "#1b5e3b" },
        neon: { DEFAULT: "#39ff88", dim: "#22c55e" },
        char: { 900: "#0b0d0c", 800: "#141816", 700: "#1d2320" },
      },
      fontFamily: { display: ['"Bricolage Grotesque"', "sans-serif"], sans: ['"Instrument Sans"', "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
