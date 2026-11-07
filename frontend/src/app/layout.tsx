import type { Metadata } from "next";
import "./globals.css";
import { LanguageProvider } from "@/components/LanguageProvider";
import { DemoBanner } from "@/components/DemoBanner";

export const metadata: Metadata = {
  title: "CareGap 360 | Longitudinal Health Records & Care Continuity",
  description: "AI-Powered Unified Health Records, Medication Intelligence & Care Continuity Platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 antialiased">
        <LanguageProvider>
          <DemoBanner />
          {children}
        </LanguageProvider>
      </body>
    </html>
  );
}
