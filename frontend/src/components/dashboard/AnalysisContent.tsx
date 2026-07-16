"use client";
import { useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

interface AnalysisContentProps {
  content: string | null;
  isLoading: boolean;
  emptyMessage?: string;
}

export default function AnalysisContent({
  content,
  isLoading,
  emptyMessage,
}: AnalysisContentProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
          <p className="text-surface-400 text-sm">Loading analysis...</p>
        </div>
      </div>
    );
  }

  if (!content) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-surface-500 text-sm">
          {emptyMessage || "Analysis not available yet. The repository is still being processed."}
        </p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="prose prose-invert max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children, ...props }) => (
            <h1 className="text-2xl font-bold text-surface-100 mt-8 mb-4" {...props}>{children}</h1>
          ),
          h2: ({ children, ...props }) => (
            <h2 className="text-xl font-semibold text-surface-100 mt-6 mb-3" {...props}>{children}</h2>
          ),
          h3: ({ children, ...props }) => (
            <h3 className="text-lg font-semibold text-surface-100 mt-5 mb-2" {...props}>{children}</h3>
          ),
          p: ({ children, ...props }) => (
            <p className="text-surface-300 leading-relaxed mb-4" {...props}>{children}</p>
          ),
          ul: ({ children, ...props }) => (
            <ul className="list-disc pl-6 mb-4 space-y-1 text-surface-300" {...props}>{children}</ul>
          ),
          ol: ({ children, ...props }) => (
            <ol className="list-decimal pl-6 mb-4 space-y-1 text-surface-300" {...props}>{children}</ol>
          ),
          li: ({ children, ...props }) => (
            <li className="text-surface-300" {...props}>{children}</li>
          ),
          code: ({ children, className, ...props }) => {
            const isInline = !className;
            if (isInline) {
              return (
                <code className="px-1.5 py-0.5 bg-surface-800 rounded text-sm text-accent font-mono" {...props}>
                  {children}
                </code>
              );
            }
            return (
              <pre className="bg-surface-900 rounded-xl p-4 overflow-x-auto border border-surface-800 mb-4">
                <code className={cn("text-sm font-mono text-surface-200", className)} {...props}>
                  {children}
                </code>
              </pre>
            );
          },
          blockquote: ({ children, ...props }) => (
            <blockquote className="border-l-4 border-accent/50 pl-4 py-2 mb-4 bg-accent/5 rounded-r-lg text-surface-400" {...props}>
              {children}
            </blockquote>
          ),
          table: ({ children, ...props }) => (
            <div className="overflow-x-auto mb-4">
              <table className="w-full border-collapse" {...props}>{children}</table>
            </div>
          ),
          th: ({ children, ...props }) => (
            <th className="border border-surface-700 px-4 py-2 bg-surface-800 text-surface-200 text-left font-semibold" {...props}>
              {children}
            </th>
          ),
          td: ({ children, ...props }) => (
            <td className="border border-surface-700 px-4 py-2 text-surface-300" {...props}>{children}</td>
          ),
          hr: (props) => <hr className="border-surface-800 my-8" {...props} />,
          a: ({ children, href, ...props }) => (
            <a href={href} className="text-accent hover:text-accent-300 underline" target="_blank" rel="noopener noreferrer" {...props}>
              {children}
            </a>
          ),
          strong: ({ children, ...props }) => (
            <strong className="font-semibold text-surface-100" {...props}>{children}</strong>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
