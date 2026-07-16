"use client";
import { useEffect, useRef } from "react";
import mermaid from "mermaid";

interface MermaidDiagramProps {
  chart: string;
}

function extractDiagrams(chart: string): string[] {
  const regex = /```mermaid\n?([\s\S]*?)```/g;
  const diagrams: string[] = [];
  let match;
  while ((match = regex.exec(chart)) !== null) {
    const content = match[1].trim();
    if (content) diagrams.push(content);
  }
  return diagrams.length > 0 ? diagrams : [chart.trim()];
}

export default function MermaidDiagram({ chart }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const initializedRef = useRef(false);

  useEffect(() => {
    if (!initializedRef.current) {
      mermaid.initialize({
        theme: "dark",
        themeVariables: {
          background: "#0f1117",
          primaryColor: "#6366f1",
          primaryTextColor: "#f1f3f9",
          primaryBorderColor: "#4f46e5",
          lineColor: "#4f46e5",
          secondaryColor: "#1a1d2e",
          tertiaryColor: "#232738",
          fontSize: "14px",
        },
        flowchart: { useMaxWidth: true },
        sequence: { useMaxWidth: true },
      });
      initializedRef.current = true;
    }
  }, []);

  useEffect(() => {
    if (!chart || !containerRef.current) return;

    const diagrams = extractDiagrams(chart);
    if (diagrams.length === 0) return;

    containerRef.current.innerHTML = "";

    diagrams.forEach((diagram, index) => {
      const id = `mermaid-${Math.random().toString(36).substring(2, 9)}-${index}`;
      const wrapper = document.createElement("div");
      wrapper.className = "mermaid-wrapper mb-4 last:mb-0";
      containerRef.current!.appendChild(wrapper);

      mermaid
        .render(id, diagram)
        .then((result) => {
          wrapper.innerHTML = result.svg;
        })
        .catch((e) => {
          wrapper.innerHTML = `<pre class="text-red-400 text-sm p-4 bg-surface-900 rounded-xl border border-surface-800">Failed to render diagram: ${e}</pre>`;
        });
    });
  }, [chart]);

  if (!chart) {
    return (
      <p className="text-surface-500 text-sm">
        No diagram available yet.
      </p>
    );
  }

  return (
    <div
      ref={containerRef}
      className="bg-surface-950 rounded-2xl p-6 border border-surface-800 overflow-x-auto flex flex-col items-center mermaid-container"
    />
  );
}
