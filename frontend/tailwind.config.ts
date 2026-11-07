import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        blue: {
          50: "#eef8f5", 100: "#d8eee7", 200: "#b5dcd0", 300: "#83bfb0",
          400: "#4e9e8d", 500: "#287e70", 600: "#17695d", 700: "#13564d",
          800: "#16463f", 900: "#153d37", 950: "#072823",
        },
        brand: {
          50: "#eff8ff",
          100: "#dbeafe",
          500: "#0284c7",
          600: "#0369a1",
          700: "#075985",
        },
        clinical: {
          success: "#059669",
          warning: "#d97706",
          danger: "#dc2626",
          neutral: "#475569",
        }
      },
    },
  },
  plugins: [],
};
export default config;

