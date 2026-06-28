import type { PaletteOptions } from '@mui/material/styles/createPalette'

/**
 * Color tokens for the backend's DecisionOutcome and ApprovalStatus
 * enum values (see backend/policy/models.py). Keys are the exact
 * lower_snake_case strings those enums serialize to over JSON - e.g.
 * DecisionOutcome.PENDING_APPROVAL.value === "pending_approval".
 * Centralized here so a status Chip on the Logs page and one on the
 * Approvals page always agree on what "blocked" looks like.
 */
export const decisionOutcomeColors: Record<string, string> = {
  allowed: '#2e7d32',
  rewritten: '#0277bd',
  pending_approval: '#ed6c02',
  approved: '#2e7d32',
  rejected: '#c62828',
  blocked: '#c62828',
  approval_timed_out: '#c62828',
  budget_exceeded: '#c62828',
}

export const palette: PaletteOptions = {
  mode: 'light',
  primary: {
    main: '#1565c0',
  },
  secondary: {
    main: '#37474f',
  },
  background: {
    default: '#f4f6f8',
    paper: '#ffffff',
  },
}