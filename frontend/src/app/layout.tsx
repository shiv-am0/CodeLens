import type { Metadata } from "next";
import "./globals.css";

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
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
