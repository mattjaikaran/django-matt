/**
 * Area Chart Component
 * A flexible area chart using SVG for data visualization
 */

import { cn } from '@/lib/utils';
import { useMemo } from 'react';

export interface AreaChartDataPoint {
  label: string;
  value: number;
}

export interface AreaChartProps {
  data: AreaChartDataPoint[];
  height?: number;
  className?: string;
  color?: string;
  gradientFrom?: string;
  gradientTo?: string;
  showGrid?: boolean;
  showLabels?: boolean;
  showValues?: boolean;
  animate?: boolean;
}

export function AreaChart({
  data,
  height = 200,
  className,
  color = 'hsl(var(--primary))',
  gradientFrom = 'hsl(var(--primary) / 0.3)',
  gradientTo = 'hsl(var(--primary) / 0.05)',
  showGrid = true,
  showLabels = true,
  showValues = false,
  animate = true,
}: AreaChartProps) {
  const { path, areaPath, points, maxValue, minValue } = useMemo(() => {
    if (data.length === 0)
      return { path: '', areaPath: '', points: [], maxValue: 0, minValue: 0 };

    const values = data.map(d => d.value);
    const max = Math.max(...values);
    const min = Math.min(...values);
    const range = max - min || 1;

    const padding = 40;
    const chartWidth = 100;
    const chartHeight = 100;
    const stepX = (chartWidth - padding * 2) / (data.length - 1 || 1);

    const pts = data.map((d, i) => ({
      x: padding + i * stepX,
      y:
        chartHeight -
        padding -
        ((d.value - min) / range) * (chartHeight - padding * 2),
      label: d.label,
      value: d.value,
    }));

    const linePath = pts
      .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`)
      .join(' ');

    const area = `${linePath} L ${pts[pts.length - 1]?.x || padding} ${chartHeight - padding} L ${padding} ${chartHeight - padding} Z`;

    return {
      path: linePath,
      areaPath: area,
      points: pts,
      maxValue: max,
      minValue: min,
    };
  }, [data]);

  const gradientId = useMemo(
    () => `area-gradient-${Math.random().toString(36).slice(2)}`,
    []
  );

  if (data.length === 0) {
    return (
      <div
        className={cn('flex items-center justify-center', className)}
        style={{ height }}
      >
        <p className="text-sm text-muted-foreground">No data available</p>
      </div>
    );
  }

  return (
    <div className={cn('relative', className)}>
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        style={{ height, width: '100%' }}
        className="overflow-visible"
      >
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={gradientFrom} />
            <stop offset="100%" stopColor={gradientTo} />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        {showGrid && (
          <g className="text-muted-foreground/20">
            {[0, 25, 50, 75, 100].map(y => (
              <line
                key={y}
                x1="40"
                y1={y}
                x2="100"
                y2={y}
                stroke="currentColor"
                strokeWidth="0.2"
                vectorEffect="non-scaling-stroke"
              />
            ))}
          </g>
        )}

        {/* Area fill */}
        <path
          d={areaPath}
          fill={`url(#${gradientId})`}
          className={animate ? 'duration-700 animate-in fade-in' : ''}
        />

        {/* Line */}
        <path
          d={path}
          fill="none"
          stroke={color}
          strokeWidth="0.8"
          vectorEffect="non-scaling-stroke"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={animate ? 'duration-500 animate-in fade-in' : ''}
        />

        {/* Data points */}
        {points.map((point, i) => (
          <circle
            key={i}
            cx={point.x}
            cy={point.y}
            r="1.2"
            fill={color}
            className={cn(
              'transition-transform hover:scale-150',
              animate && 'duration-300 animate-in zoom-in'
            )}
            style={{ animationDelay: `${i * 50}ms` }}
          />
        ))}
      </svg>

      {/* Labels */}
      {showLabels && (
        <div className="mt-2 flex justify-between px-2">
          {data.map((d, i) => (
            <span
              key={i}
              className="truncate text-xs text-muted-foreground"
              style={{ maxWidth: `${100 / data.length}%` }}
            >
              {d.label}
            </span>
          ))}
        </div>
      )}

      {/* Value indicators */}
      {showValues && (
        <div className="absolute right-0 top-0 flex flex-col text-xs text-muted-foreground">
          <span>{maxValue.toLocaleString()}</span>
          <span className="mt-auto">{minValue.toLocaleString()}</span>
        </div>
      )}
    </div>
  );
}
