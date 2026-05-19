/**
 * Donut Chart Component
 * A flexible donut/pie chart using SVG for data visualization
 */

import { cn } from '@/lib/utils';
import { useMemo } from 'react';

export interface DonutChartDataPoint {
  label: string;
  value: number;
  color: string;
}

export interface DonutChartProps {
  data: DonutChartDataPoint[];
  size?: number;
  thickness?: number;
  className?: string;
  showLegend?: boolean;
  showLabels?: boolean;
  showCenter?: boolean;
  centerLabel?: string;
  centerValue?: string | number;
  animate?: boolean;
}

export function DonutChart({
  data,
  size = 200,
  thickness = 30,
  className,
  showLegend = true,
  showLabels = false,
  showCenter = true,
  centerLabel,
  centerValue,
  animate = true,
}: DonutChartProps) {
  const { segments, total } = useMemo(() => {
    const sum = data.reduce((acc, d) => acc + d.value, 0);

    if (sum === 0) return { segments: [], total: 0 };

    let cumulativeAngle = -90; // Start from top
    const radius = 50 - thickness / 2;
    const circumference = 2 * Math.PI * radius;

    const segs = data.map(d => {
      const percentage = (d.value / sum) * 100;
      const angle = (d.value / sum) * 360;
      const startAngle = cumulativeAngle;

      // Calculate arc path
      const dashArray = (percentage / 100) * circumference;
      const dashOffset = ((cumulativeAngle + 90) / 360) * circumference;

      cumulativeAngle += angle;

      return {
        ...d,
        percentage,
        startAngle,
        endAngle: cumulativeAngle,
        dashArray,
        dashOffset,
        radius,
        circumference,
      };
    });

    return { segments: segs, total: sum };
  }, [data, thickness]);

  if (data.length === 0 || total === 0) {
    return (
      <div
        className={cn('flex items-center justify-center', className)}
        style={{ width: size, height: size }}
      >
        <p className="text-sm text-muted-foreground">No data available</p>
      </div>
    );
  }

  return (
    <div className={cn('flex items-center gap-6', className)}>
      {/* Chart */}
      <div className="relative" style={{ width: size, height: size }}>
        <svg viewBox="0 0 100 100" className="-rotate-90 transform">
          {segments.map((segment, i) => (
            <circle
              key={i}
              cx="50"
              cy="50"
              r={segment.radius}
              fill="none"
              stroke={segment.color}
              strokeWidth={thickness}
              strokeDasharray={`${segment.dashArray} ${segment.circumference}`}
              strokeDashoffset={-segment.dashOffset}
              className={cn(
                'transition-all duration-700',
                animate && 'animate-in fade-in zoom-in'
              )}
              style={{ animationDelay: `${i * 100}ms` }}
            />
          ))}
        </svg>

        {/* Center content */}
        {showCenter && (
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            {centerValue !== undefined && (
              <span className="text-2xl font-bold">
                {typeof centerValue === 'number'
                  ? centerValue.toLocaleString()
                  : centerValue}
              </span>
            )}
            {centerLabel && (
              <span className="text-sm text-muted-foreground">
                {centerLabel}
              </span>
            )}
          </div>
        )}

        {/* Percentage labels on chart */}
        {showLabels &&
          segments.map((segment, i) => {
            const midAngle =
              ((segment.startAngle + segment.endAngle) / 2) * (Math.PI / 180);
            const labelRadius = 50 - thickness - 5;
            const x = 50 + labelRadius * Math.cos(midAngle);
            const y = 50 + labelRadius * Math.sin(midAngle);

            return segment.percentage > 5 ? (
              <span
                key={i}
                className="absolute text-xs font-medium"
                style={{
                  left: `${x}%`,
                  top: `${y}%`,
                  transform: 'translate(-50%, -50%)',
                }}
              >
                {Math.round(segment.percentage)}%
              </span>
            ) : null;
          })}
      </div>

      {/* Legend */}
      {showLegend && (
        <div className="flex flex-col gap-2">
          {segments.map((segment, i) => (
            <div key={i} className="flex items-center gap-2">
              <div
                className="h-3 w-3 rounded-full"
                style={{ backgroundColor: segment.color }}
              />
              <span className="text-sm text-muted-foreground">
                {segment.label}
              </span>
              <span className="ml-auto text-sm font-medium">
                {segment.value.toLocaleString()}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
