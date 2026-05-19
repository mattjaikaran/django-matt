/**
 * API Layer Exports
 * Utilities for the API layer
 *
 * Note: Base api client exports come from @/lib/api (the original api.ts file)
 * Domain-specific API functions live in @/api/ (auth.ts, todos.ts)
 */

// Utilities
export {
  createErrorResponse,
  createPaginatedKey,
  createQueryKeyFactory,
  createSuccessResponse,
  handlePaginatedResponse,
  serializeParams,
} from './utils';
