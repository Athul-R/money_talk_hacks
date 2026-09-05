/**
 * The lineage canvas: React Flow with clay nodes on a dot grid. The camera
 * follows the story — every new beat refits the view unless the operator has
 * taken the wheel (pan/zoom), and "fit" hands control back.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Background, BackgroundVariant, ReactFlow, ReactFlowProvider, useReactFlow,
  type Edge, type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Focus, Landmark } from "lucide-react";
import { nodeTypes } from "./nodes";

type CanvasProps = {
  nodes: Node[]; edges: Edge[]; beatKey: string;
  selected: string | null; onSelect: (id: string | null) => void;
};

function Canvas({ nodes, edges, beatKey, onSelect }: CanvasProps) {
  const { fitView } = useReactFlow();
  const [manual, setManual] = useState(false);
  const manualRef = useRef(manual);
  manualRef.current = manual;
  const runKey = beatKey.split(":")[0];

  const refit = useCallback((force = false) => {
    if (!force && manualRef.current) return;
    // rAF so newly-mounted nodes have dimensions before framing them.
    requestAnimationFrame(() =>
      fitView({ padding: 0.15, duration: 650, maxZoom: 1.1 }));
  }, [fitView]);

  // a new run hands the camera back to the story
  useEffect(() => { setManual(false); }, [runKey]);
  useEffect(() => { refit(); }, [beatKey, refit]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.15, maxZoom: 1.1 }}
      minZoom={0.2}
      maxZoom={2.2}
      proOptions={{ hideAttribution: true }}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      onNodeClick={(_, node) => onSelect(node.id)}
      onPaneClick={() => onSelect(null)}
      // event is defined only for USER gestures; programmatic fits pass none
      onMoveStart={(event) => { if (event) setManual(true); }}
      zoomOnDoubleClick={false}
    >
      <Background variant={BackgroundVariant.Dots} gap={22} size={1.2}
                  color="color-mix(in oklab, var(--foreground) 12%, transparent)" />
      <button
        type="button"
        onClick={() => { setManual(false); refit(true); }}
        className="clay-pill absolute bottom-4 right-4 z-10 flex h-9 items-center gap-1.5 rounded-full px-3 text-[11px] font-semibold"
        style={{ color: manual ? "var(--ring-engine)" : "var(--muted-foreground)" }}
      >
        <Focus className="h-4 w-4" strokeWidth={2.4} /> fit
      </button>
    </ReactFlow>
  );
}

export function StoryGraph(props: CanvasProps) {
  const empty = props.nodes.length === 0;
  return (
    <div className="clay-canvas relative min-h-0 flex-1 overflow-hidden rounded-[28px]">
      <div className="dot-grid pointer-events-none absolute inset-0 opacity-60" />
      <div className="absolute inset-0">
        <ReactFlowProvider>
          <Canvas {...props} />
        </ReactFlowProvider>
      </div>
      {empty && (
        <div className="pointer-events-none absolute inset-0 grid place-items-center p-6">
          <div className="clay-empty grid max-w-[360px] place-items-center gap-2 rounded-[24px] px-8 py-9 text-center">
            <Landmark className="h-7 w-7" style={{ color: "var(--ring-engine)" }} strokeWidth={1.8} />
            <p className="text-[13px] font-semibold text-foreground">No lineage yet</p>
            <p className="text-[11.5px] leading-relaxed text-muted-foreground">
              Pick a run on the left — the variance engine's beats grow here:
              metric → router → branches → drill → explanation.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
