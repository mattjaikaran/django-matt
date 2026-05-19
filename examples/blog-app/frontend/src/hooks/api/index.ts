/**
 * API Hooks Exports
 * Generic hooks for API operations
 */

export {
  useApiDelete,
  useApiDeleteById,
  useApiGet,
  useApiInfinite,
  useApiPatch,
  useApiPost,
  useApiPut,
  useApiQuery,
  useInvalidate,
  usePrefetch,
} from './use-api';

export {
  useOptimisticAdd,
  useOptimisticMutation,
  useOptimisticRemove,
  useOptimisticUpdate,
} from './use-optimistic';
