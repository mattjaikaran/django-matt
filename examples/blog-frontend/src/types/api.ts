/**
 * API-related types
 * Compatible with Django Ninja response format
 */

/**
 * Standard API response wrapper
 * Django Ninja typically returns data directly or with a success wrapper
 */
export interface ApiResponse<T = unknown> {
  data: T;
  message?: string;
  success: boolean;
}

/**
 * Django Ninja error response format
 */
export interface ApiError {
  message: string;
  code?: string;
  details?: Record<string, string | string[]>;
}

/**
 * Django Ninja validation error format
 */
export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface ValidationErrorResponse {
  detail: ValidationError[];
}

/**
 * Django Ninja paginated response format
 * Compatible with django-ninja-pagination
 */
export interface DjangoPaginatedResponse<T> {
  items: T[];
  count: number;
  page: number;
  page_size: number;
  pages: number;
}

/**
 * Standard paginated response format
 * Used by default in the boilerplate
 */
export interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
}

/**
 * Converts Django Ninja pagination to standard format
 */
export function normalizePaginatedResponse<T>(
  response: DjangoPaginatedResponse<T>
): PaginatedResponse<T> {
  return {
    data: response.items,
    pagination: {
      page: response.page,
      limit: response.page_size,
      total: response.count,
      totalPages: response.pages,
    },
  };
}

/**
 * Query parameters for list endpoints
 */
export interface QueryParams {
  page?: number;
  page_size?: number;
  search?: string;
  ordering?: string;
  filters?: Record<string, string | number | boolean>;
}

/**
 * Filter operators for advanced filtering
 */
export type FilterOperator =
  | 'eq'
  | 'ne'
  | 'gt'
  | 'gte'
  | 'lt'
  | 'lte'
  | 'contains'
  | 'icontains'
  | 'in'
  | 'isnull';

export interface FilterParam {
  field: string;
  operator: FilterOperator;
  value: string | number | boolean | (string | number)[];
}
