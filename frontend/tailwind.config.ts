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

