import type { Metadata } from "next";
import "./globals.css";
import { AIConfigurationProvider } from "@/components/settings/AIConfigurationProvider";

export const metadata: Metadata = {
  title: "CodeLens - Understand Any Codebase in Minutes",
  description:
    "Paste any public GitHub repository and instantly receive AI-generated documentation, architecture diagrams, onboarding guidance, and intelligent answers.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen">
        <AIConfigurationProvider>{children}</AIConfigurationProvider>
      </body>
    </html>
  );
}
