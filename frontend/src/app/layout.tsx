import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CareGap 360 | Longitudinal Health Records & Care Continuity",
  description: "AI-Powered Unified Health Records, Medication Intelligence & Care Continuity Platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 antialiased">{children}</body>
    </html>
  );
}

