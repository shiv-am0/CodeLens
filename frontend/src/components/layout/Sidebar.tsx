"use client";
import { useMemo } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Code2,
  LayoutDashboard,
  GitBranch,
  FileJson,
  Database,
  FileText,
  Share2,
  MessageSquare,
  Lightbulb,
  ArrowLeft,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface SidebarProps {
  repoId: string;
}

const navItems = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "architecture", label: "Architecture", icon: GitBranch },
  { id: "folders", label: "Folder Explorer", icon: FileJson },
  { id: "api", label: "API Documentation", icon: FileText },
  { id: "database", label: "Database", icon: Database },
  { id: "diagram", label: "Mermaid Diagram", icon: Share2 },
  { id: "readme", label: "README", icon: FileText },
  { id: "suggestions", label: "Suggestions", icon: Lightbulb },
  { id: "chat", label: "Ask AI", icon: MessageSquare },
];

export default function Sidebar({ repoId }: SidebarProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentSection = searchParams.get("section") || "overview";

  return (
    <aside className="w-64 h-screen glass border-r border-surface-800/50 flex flex-col">
      <div className="p-4 border-b border-surface-800/50">
        <Link
          href="/"
          className="flex items-center gap-2 text-surface-400 hover:text-surface-100 transition-colors mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm">Back to Home</span>
        </Link>
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center">
            <Code2 className="w-4 h-4 text-white" />
          </div>
          <span className="font-semibold text-surface-100">CodeLens</span>
        </div>
      </div>

      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => (
          <Link
            key={item.id}
            href={`/dashboard?id=${repoId}&section=${item.id}`}
            className={cn(
              "sidebar-item text-sm",
              currentSection === item.id && "active"
            )}
          >
            <item.icon className="w-4 h-4" />
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
