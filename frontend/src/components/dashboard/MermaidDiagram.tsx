"use client";
import { useEffect, useRef, useState } from "react";
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
  const dragRef = useRef({ isDragging: false, startX: 0, startY: 0, lastPanX: 0, lastPanY: 0 });

  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });

  const zoomRef = useRef(zoom);
  const panRef = useRef(pan);
  zoomRef.current = zoom;
  panRef.current = pan;

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
      containerRef.current!.appendChild(wrapper);

      mermaid
        .render(id, diagram)
        .then((result) => {
          wrapper.innerHTML = result.svg;
          const svg = wrapper.querySelector("svg");
          if (svg) {
            svg.style.maxWidth = "none";
            svg.style.display = "block";
          }
        })
        .catch((e) => {
          wrapper.innerHTML = `<pre class="text-red-400 text-sm p-4 bg-surface-900 rounded-xl border border-surface-800">Failed to render diagram: ${e}</pre>`;
        });
    });

    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, [chart]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      setZoom((prev) => Math.max(0.1, Math.min(5, prev * delta)));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const onPointerDown = (e: PointerEvent) => {
      dragRef.current = {
        isDragging: true,
        startX: e.clientX,
        startY: e.clientY,
        lastPanX: panRef.current.x,
        lastPanY: panRef.current.y,
      };
      el.setPointerCapture(e.pointerId);
    };

    const onPointerMove = (e: PointerEvent) => {
      if (!dragRef.current.isDragging) return;
      const dx = e.clientX - dragRef.current.startX;
      const dy = e.clientY - dragRef.current.startY;
      setPan({
        x: dragRef.current.lastPanX + dx,
        y: dragRef.current.lastPanY + dy,
      });
    };

    const onPointerUp = (e: PointerEvent) => {
      dragRef.current.isDragging = false;
      el.releasePointerCapture(e.pointerId);
    };

    el.addEventListener("pointerdown", onPointerDown);
    el.addEventListener("pointermove", onPointerMove);
    el.addEventListener("pointerup", onPointerUp);

    return () => {
      el.removeEventListener("pointerdown", onPointerDown);
      el.removeEventListener("pointermove", onPointerMove);
      el.removeEventListener("pointerup", onPointerUp);
    };
  }, []);

  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const zoomIn = () => setZoom((prev) => Math.min(5, prev * 1.25));
  const zoomOut = () => setZoom((prev) => Math.max(0.1, prev * 0.8));

  if (!chart) {
    return (
      <p className="text-surface-500 text-sm">
        No diagram available yet.
      </p>
    );
  }

  return (
    <div className="relative w-full h-full overflow-hidden rounded-2xl border border-surface-800 bg-surface-950" style={{ touchAction: "none" }}>
      <div
        ref={containerRef}
        className="w-full h-full cursor-grab active:cursor-grabbing"
        style={{
          transform: `scale(${zoom}) translate(${pan.x}px, ${pan.y}px)`,
          transformOrigin: "0 0",
        }}
      />
      <div className="absolute bottom-3 right-3 flex items-center gap-1.5 bg-surface-900/90 backdrop-blur-sm rounded-lg border border-surface-700 p-1.5 z-10">
        <button onClick={zoomOut} className="w-7 h-7 flex items-center justify-center text-surface-300 hover:text-surface-100 hover:bg-surface-700 rounded text-sm font-medium">−</button>
        <span className="text-xs text-surface-400 w-10 text-center tabular-nums select-none">{Math.round(zoom * 100)}%</span>
        <button onClick={zoomIn} className="w-7 h-7 flex items-center justify-center text-surface-300 hover:text-surface-100 hover:bg-surface-700 rounded text-sm font-medium">+</button>
        <span className="w-px h-5 bg-surface-700" />
        <button onClick={resetView} className="w-7 h-7 flex items-center justify-center text-surface-300 hover:text-surface-100 hover:bg-surface-700 rounded text-xs font-medium">⟲</button>
      </div>
    </div>
  );
}
