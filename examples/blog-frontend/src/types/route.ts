/**
 * Route-related types
 */

export interface RouteConfig {
  path: string;
  component: React.ComponentType;
  layout?: React.ComponentType;
  requiresAuth?: boolean;
  title?: string;
}
