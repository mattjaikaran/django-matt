/**
 * Base types used throughout the application
 */

export interface BaseEntity {
  id: string;
  createdAt: string;
  updatedAt: string;
}

export interface ComponentProps {
  className?: string;
  children?: React.ReactNode;
}

export interface PageProps extends ComponentProps {
  title?: string;
  description?: string;
}

export type Theme = 'light' | 'dark' | 'system';
