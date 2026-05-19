/**
 * Stat Card Component
 * A card for displaying key metrics with optional trend indicators
 */

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { LucideIcon, Minus, TrendingDown, TrendingUp } from 'lucide-react';

export interface StatCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon?: LucideIcon;
  trend?: {
    value: number;
    label?: string;
    isPositiveGood?: boolean;
  };
  className?: string;
  loading?: boolean;
}

export function StatCard({
  title,
  value,
  description,
  icon: Icon,
  trend,
  className,
  loading = false,
}: StatCardProps) {
  const getTrendInfo = () => {
    if (!trend) return null;

    const isPositive = trend.value > 0;
    const isNeutral = trend.value === 0;
    const isGood = trend.isPositiveGood !== false ? isPositive : !isPositive;

    return {
      icon: isNeutral ? Minus : isPositive ? TrendingUp : TrendingDown,
      color: isNeutral
        ? 'text-muted-foreground'
        : isGood
          ? 'text-emerald-500'
          : 'text-rose-500',
      bgColor: isNeutral
        ? 'bg-muted'
        : isGood
          ? 'bg-emerald-500/10'
          : 'bg-rose-500/10',
      prefix: isPositive ? '+' : '',
    };
  };

  const trendInfo = getTrendInfo();

  if (loading) {
    return (
      <Card className={cn('animate-pulse', className)}>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <div className="h-4 w-24 rounded bg-muted" />
          <div className="h-8 w-8 rounded bg-muted" />
        </CardHeader>
        <CardContent>
          <div className="mb-2 h-8 w-20 rounded bg-muted" />
          <div className="h-3 w-32 rounded bg-muted" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn('transition-all hover:shadow-md', className)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        {Icon && (
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10">
            <Icon className="h-4 w-4 text-primary" />
          </div>
        )}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">
          {typeof value === 'number' ? value.toLocaleString() : value}
        </div>

        <div className="mt-1 flex items-center gap-2">
          {trendInfo && (
            <div
              className={cn(
                'flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium',
                trendInfo.bgColor,
                trendInfo.color
              )}
            >
              <trendInfo.icon className="h-3 w-3" />
              <span>
                {trendInfo.prefix}
                {Math.abs(trend!.value)}%
              </span>
            </div>
          )}

          {(description || trend?.label) && (
            <p className="text-xs text-muted-foreground">
              {trend?.label || description}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
