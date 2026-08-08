/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: {
          950: "#0A0E14",
          900: "#0F1420",
          800: "#161C2C",
          700: "#212A3E",
          600: "#2E3A54",
        },
        ink: {
          100: "#E8ECF4",
          300: "#AAB4C8",
          500: "#6B7690",
        },
        status: {
          pass: "#3DDC97",
          fail: "#F1554C",
          critical: "#FF3B6B",
          warn: "#F5B942",
          info: "#4FA9E8",
        },
      },
      fontFamily: {
        display: ["'Space Grotesk'", "sans-serif"],
        sans: ["'Inter'", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
    },
  },
  plugins: [],
};
