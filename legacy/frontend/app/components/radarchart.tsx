// components/radarchart.tsx - v4.2
"use client";

import { GameScores, METRIC_LABELS } from "../types";

interface RadarChartProps {
  scores: GameScores;
  statusColor: string;
  size?: number;
}

const CHART_METRICS = [
  "replay_value",
  "addictiveness",
  "difficulty",
  "originality",
  "atmosphere_intensity",
  "story_depth",
];

export default function RadarChart({
  scores,
  statusColor,
  size = 200,
}: RadarChartProps) {
  const center = size / 2;
  const radius = size * 0.36;
  const angleStep = (Math.PI * 2) / CHART_METRICS.length;

  const getPoint = (index: number, value: number) => {
    const clampedValue = Math.min(value, 100);
    const angle = angleStep * index - Math.PI / 2;
    const r = (clampedValue / 100) * radius;
    return {
      x: center + r * Math.cos(angle),
      y: center + r * Math.sin(angle),
    };
  };

  const getLabelPoint = (index: number) => {
    const angle = angleStep * index - Math.PI / 2;
    const r = radius + 20;
    return {
      x: center + r * Math.cos(angle),
      y: center + r * Math.sin(angle),
    };
  };

  const dataPoints = CHART_METRICS.map((metric, i) => {
    const rawScore = scores[metric as keyof GameScores] || 50;
    return getPoint(i, rawScore);
  });

  const polygonPath =
    dataPoints.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ") +
    " Z";

  const gridLevels = [25, 50, 75, 100];

  return (
    <div className="flex justify-center">
      <svg width={size} height={size} className="overflow-visible">
        {gridLevels.map((level) => {
          const gridPoints = CHART_METRICS.map((_, i) => getPoint(i, level));
          const gridPath =
            gridPoints
              .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`)
              .join(" ") + " Z";
          return (
            <path
              key={level}
              d={gridPath}
              fill="none"
              stroke="rgba(255,255,255,0.1)"
              strokeWidth={1}
            />
          );
        })}

        {CHART_METRICS.map((_, i) => {
          const point = getPoint(i, 100);
          return (
            <line
              key={i}
              x1={center}
              y1={center}
              x2={point.x}
              y2={point.y}
              stroke="rgba(255,255,255,0.1)"
              strokeWidth={1}
            />
          );
        })}

        <path
          d={polygonPath}
          fill={statusColor}
          fillOpacity={0.25}
          stroke={statusColor}
          strokeWidth={2}
        />

        {dataPoints.map((point, i) => (
          <circle key={i} cx={point.x} cy={point.y} r={3} fill={statusColor} />
        ))}

        {CHART_METRICS.map((metric, i) => {
          const labelPoint = getLabelPoint(i);
          const rawScore = scores[metric as keyof GameScores] || 50;
          const shortLabel = (METRIC_LABELS[metric] || metric).slice(0, 4);

          return (
            <g key={metric}>
              <text
                x={labelPoint.x}
                y={labelPoint.y - 5}
                textAnchor="middle"
                dominantBaseline="middle"
                className="fill-gray-400"
                style={{ fontSize: "9px" }}
              >
                {shortLabel}
              </text>
              <text
                x={labelPoint.x}
                y={labelPoint.y + 7}
                textAnchor="middle"
                dominantBaseline="middle"
                className="fill-white font-bold"
                style={{ fontSize: "10px" }}
              >
                {rawScore}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
