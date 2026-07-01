import { useMemo, useState } from 'react';
import { useQueries } from '@tanstack/react-query';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  InputAdornment,
  LinearProgress,
  Paper,
  Skeleton,
  Snackbar,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import TokenIcon from '@mui/icons-material/Token';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import RefreshIcon from '@mui/icons-material/Refresh';
import EditIcon from '@mui/icons-material/Edit';
import SearchIcon from '@mui/icons-material/Search';

import { BUDGETS_QUERY_KEY, useBudgets, useUpdateBudget, useResetBudget } from '../hooks/useBudgets';
import { getConversationBudgetState } from '../api';
import type { BudgetResponse } from '../types/budgets';

function UsageBar({ used, max }: { used: number; max: number }) {
  const pct = max > 0 ? Math.min((used / max) * 100, 100) : 0;
  const color = pct >= 80 ? 'error' : pct >= 50 ? 'warning' : 'primary';
  return (
    <Box sx={{ minWidth: 120 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
        <Typography variant="caption" color={pct >= 80 ? 'error.main' : 'text.secondary'}>{pct.toFixed(0)}%</Typography>
        <Typography variant="caption" color="text.secondary">{used.toLocaleString()} / {max.toLocaleString()}</Typography>
      </Box>
      <LinearProgress variant="determinate" value={pct} color={color} sx={{ height: 6, borderRadius: 3 }} />
    </Box>
  );
}

export default function BudgetsPage() {
  const { data: budgets = [], isLoading, isError, error } = useBudgets();
  const updateBudget = useUpdateBudget();
  const resetBudget = useResetBudget();

  const budgetStateQueries = useQueries({
    queries: budgets.map((budget) => ({
      queryKey: [...BUDGETS_QUERY_KEY, budget.conversationid, 'state'] as const,
      queryFn: () => getConversationBudgetState(budget.conversationid as string),
      enabled: Boolean(budget.conversationid),
      staleTime: 10_000,
    })),
  });

  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const [editOpen, setEditOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<BudgetResponse | null>(null);
  const [newMax, setNewMax] = useState('');

  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false, message: '', severity: 'success',
  });

  const notify = (message: string, severity: 'success' | 'error') =>
    setSnackbar({ open: true, message, severity });

  const usageByConversationId: Record<string, number> = useMemo(() => {
    const result: Record<string, number> = {};
    budgets.forEach((budget, index) => {
      if (budget.conversationid) {
        result[budget.conversationid] = budgetStateQueries[index]?.data?.totaltokens ?? 0;
      }
    });
    return result;
  }, [budgets, budgetStateQueries]);

  const totalBudget = budgets.reduce((sum, budget) => sum + budget.maxtokens, 0);
  const totalUsed = Object.values(usageByConversationId).reduce((sum, value) => sum + value, 0);
  const remaining = totalBudget - totalUsed;

  const filtered = useMemo(() => {
    if (!search) return budgets;
    return budgets.filter((budget) => budget.conversationid?.toLowerCase().includes(search.toLowerCase()));
  }, [budgets, search]);

  const paginated = filtered.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);

  async function handleEditSave() {
    if (!editTarget?.conversationid) return;
    const maxTokens = parseInt(newMax, 10);
    if (!maxTokens || maxTokens <= 0) {
      notify('Enter a valid token limit.', 'error');
      return;
    }
    try {
      await updateBudget.mutateAsync({
        conversationId: editTarget.conversationid,
        payload: { max_tokens: maxTokens },
      });
      notify('Budget updated.', 'success');
      setEditOpen(false);
    } catch (e) {
      notify(e instanceof Error ? e.message : 'Update failed.', 'error');
    }
  }

  async function handleReset(conversationId: string) {
    try {
      await resetBudget.mutateAsync(conversationId);
      notify('Budget reset to default.', 'success');
    } catch (e) {
      notify(e instanceof Error ? e.message : 'Reset failed.', 'error');
    }
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" fontWeight={700}>Budgets</Typography>
        <Typography variant="body1" color="text.secondary">Inspect and adjust conversation token budgets.</Typography>
      </Box>

      {isError && (
        <Alert severity="error">{error instanceof Error ? error.message : 'Failed to load budgets.'}</Alert>
      )}

      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} lg={3}>
          <Card>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="overline" color="text.secondary">Total Budget</Typography>
                  {isLoading ? <Skeleton width={80} height={40} /> : <Typography variant="h5" fontWeight={700}>{totalBudget.toLocaleString()}</Typography>}
                </Box>
                <AccountBalanceWalletIcon color="primary" />
              </Stack>
              <Typography variant="caption" color="text.secondary">across {budgets.length} conversations</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <Card>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="overline" color="text.secondary">Remaining Tokens</Typography>
                  {isLoading ? <Skeleton width={80} height={40} /> : <Typography variant="h5" fontWeight={700} color={remaining < totalBudget * 0.2 ? 'error.main' : 'inherit'}>{remaining.toLocaleString()}</Typography>}
                </Box>
                <TokenIcon color="success" />
              </Stack>
              <Typography variant="caption" color="text.secondary">estimated across all conversations</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <Card>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="overline" color="text.secondary">Tokens Used</Typography>
                  {isLoading ? <Skeleton width={80} height={40} /> : <Typography variant="h5" fontWeight={700}>{totalUsed.toLocaleString()}</Typography>}
                </Box>
                <TrendingUpIcon color="warning" />
              </Stack>
              <Typography variant="caption" color="text.secondary">{totalBudget > 0 ? ((totalUsed / totalBudget) * 100).toFixed(1) : 0}% of total budget consumed</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <Card>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="overline" color="text.secondary">Active Conversations</Typography>
                  {isLoading ? <Skeleton width={60} height={40} /> : <Typography variant="h5" fontWeight={700}>{budgets.length}</Typography>}
                </Box>
                <AccountBalanceWalletIcon color="action" />
              </Stack>
              <Typography variant="caption" color="text.secondary">with configured token limits</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <TextField
        size="small"
        placeholder="Search by conversation ID…"
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
          setPage(0);
        }}
        InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> }}
        sx={{ maxWidth: 320 }}
      />

      {isLoading ? (
        <Stack spacing={1}>
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} variant="rectangular" height={56} sx={{ borderRadius: 1 }} />)}
        </Stack>
      ) : filtered.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: 'center' }}>
          <TokenIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
          <Typography variant="h6" gutterBottom>No budget configurations found</Typography>
          <Typography variant="body2" color="text.secondary">Budget entries will appear here once conversations are tracked.</Typography>
        </Paper>
      ) : (
        <Paper variant="outlined">
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Conversation ID</TableCell>
                  <TableCell>Budget Limit</TableCell>
                  <TableCell sx={{ minWidth: 200 }}>Usage</TableCell>
                  <TableCell>Remaining</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {paginated.map((budget) => {
                  const conversationId = budget.conversationid ?? 'default';
                  const used = usageByConversationId[budget.conversationid ?? ''] ?? 0;
                  const rowRemaining = budget.maxtokens - used;
                  return (
                    <TableRow key={conversationId} hover>
                      <TableCell><Typography variant="body2" fontFamily="monospace">{conversationId}</Typography></TableCell>
                      <TableCell><Typography variant="body2">{budget.maxtokens.toLocaleString()} tokens</Typography></TableCell>
                      <TableCell><UsageBar used={used} max={budget.maxtokens} /></TableCell>
                      <TableCell>
                        <Typography variant="body2" color={rowRemaining < budget.maxtokens * 0.2 ? 'error.main' : 'inherit'}>
                          {rowRemaining.toLocaleString()}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Stack direction="row" justifyContent="flex-end" spacing={0.5}>
                          {budget.conversationid && (
                            <>
                              <Tooltip title="Edit Budget">
                                <Button
                                  size="small"
                                  startIcon={<EditIcon />}
                                  onClick={() => {
                                    setEditTarget(budget);
                                    setNewMax(String(budget.maxtokens));
                                    setEditOpen(true);
                                  }}
                                >
                                  Edit
                                </Button>
                              </Tooltip>
                              <Tooltip title="Reset to Default">
                                <Button
                                  size="small"
                                  color="warning"
                                  startIcon={<RefreshIcon />}
                                  onClick={() => handleReset(budget.conversationid!)}
                                  disabled={resetBudget.isPending}
                                >
                                  Reset
                                </Button>
                              </Tooltip>
                            </>
                          )}
                        </Stack>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
          <TablePagination
            component="div"
            count={filtered.length}
            page={page}
            rowsPerPage={rowsPerPage}
            onPageChange={(_, nextPage) => setPage(nextPage)}
            onRowsPerPageChange={(e) => {
              setRowsPerPage(parseInt(e.target.value, 10));
              setPage(0);
            }}
            rowsPerPageOptions={[5, 10, 25]}
          />
        </Paper>
      )}

      <Dialog open={editOpen} onClose={() => setEditOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Edit Budget — {editTarget?.conversationid}</DialogTitle>
        <DialogContent>
          <TextField
            label="Max Tokens"
            type="number"
            value={newMax}
            onChange={(e) => setNewMax(e.target.value)}
            fullWidth
            sx={{ mt: 1 }}
            inputProps={{ min: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleEditSave} disabled={updateBudget.isPending}>
            {updateBudget.isPending ? 'Saving…' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((state) => ({ ...state, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert severity={snackbar.severity} onClose={() => setSnackbar((state) => ({ ...state, open: false }))}>{snackbar.message}</Alert>
      </Snackbar>
    </Stack>
  );
}
