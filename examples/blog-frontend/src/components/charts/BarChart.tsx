/**
 * Bar Chart Component
 * A flexible bar chart using SVG for data visualization
 */

import { cn } from '@/lib/utils';
import { useMemo } from 'react';

export interface BarChartDataPoint {
  label: string;
  value: number;
  color?: string;
}

export interface BarChartProps {
  data: BarChartDataPoint[];
  height?: number;
  className?: string;
  color?: string;
  showLabels?: boolean;
  showValues?: boolean;
  horizontal?: boolean;
  animate?: boolean;
  gap?: number;
}

export function BarChart({
  data,
  height = 200,
  className,
  color = 'hsl(var(--primary))',
  showLabels = true,
  showValues = true,
  horizontal = false,
  animate = true,
  gap = 8,
}: BarChartProps) {
  const { bars } = useMemo(() => {
    if (data.length === 0) return { bars: [], maxValue: 0 };

    const max = Math.max(...data.map(d => d.value));

    const barsData = data.map((d, i) => ({
      ...d,
      percentage: max > 0 ? (d.value / max) * 100 : 0,
      index: i,
    }));

    return { bars: barsData, maxValue: max };
  }, [data]);

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

  if (horizontal) {
    return (
      <div className={cn('space-y-3', className)} style={{ minHeight: height }}>
        {bars.map((bar, i) => (
          <div key={i} className="space-y-1">
            <div className="flex justify-between text-sm">
              <span className="max-w-[60%] truncate text-muted-foreground">
                {bar.label}
              </span>
              {showValues && (
                <span className="font-medium">
                  {bar.value.toLocaleString()}
                </span>
              )}
            </div>
            <div className="h-3 overflow-hidden rounded-full bg-muted">
              <div
                className={cn(
                  'h-full rounded-full transition-all duration-500',
                  animate && 'animate-in slide-in-from-left'
                )}
                style={{
                  width: `${bar.percentage}%`,
                  backgroundColor: bar.color || color,
                  animationDelay: `${i * 100}ms`,
                }}
              />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className={cn('flex flex-col', className)} style={{ height }}>
      {/* Chart area */}
      <div className="flex flex-1 items-end" style={{ gap }}>
        {bars.map((bar, i) => (
          <div
            key={i}
            className="flex h-full flex-1 flex-col items-center justify-end"
          >
            {/* Value label */}
            {showValues && (
              <span className="mb-1 text-xs font-medium">
                {bar.value.toLocaleString()}
              </span>
            )}

            {/* Bar */}
            <div
              className={cn(
                'w-full rounded-t-md transition-all duration-500',
                animate && 'animate-in slide-in-from-bottom'
              )}
              style={{
                height: `${bar.percentage}%`,
                backgroundColor: bar.color || color,
                minHeight: bar.value > 0 ? 4 : 0,
                animationDelay: `${i * 100}ms`,
              }}
            />
          </div>
        ))}
      </div>

      {/* Labels */}
      {showLabels && (
        <div className="mt-2 flex" style={{ gap }}>
          {bars.map((bar, i) => (
            <span
              key={i}
              className="flex-1 truncate text-center text-xs text-muted-foreground"
            >
              {bar.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
