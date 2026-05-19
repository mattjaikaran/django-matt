/**
 * Form-related types
 */

export interface FormState {
  isSubmitting: boolean;
  errors: Record<string, string>;
  isDirty: boolean;
  isValid: boolean;
}
