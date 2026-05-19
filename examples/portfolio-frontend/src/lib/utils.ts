import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

export function formatDateRange(startDate: string, endDate: string | null, isCurrent: boolean): string {
  const start = new Date(startDate).toLocaleDateString('en-US', { year: 'numeric', month: 'short' });
  if (isCurrent) return `${start} — Present`;
  if (!endDate) return start;
  const end = new Date(endDate).toLocaleDateString('en-US', { year: 'numeric', month: 'short' });
  return `${start} — ${end}`;
}
