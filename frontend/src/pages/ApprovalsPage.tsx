import { useState, useMemo } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  FormControl,
  Grid,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Paper,
  Select,
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
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import VisibilityIcon from '@mui/icons-material/Visibility';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import SearchIcon from '@mui/icons-material/Search';

import { useAllApprovals, useApproveRequest, useRejectRequest } from '../hooks/useApprovals';
import type { ApprovalRequest, ApprovalStatus } from '../types/approvals';

function formatDate(iso: string) {
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function statusChip(status: ApprovalStatus) {
  const map: Record<ApprovalStatus, { color: 'warning' | 'success' | 'error' | 'default'; label: string }> = {
    pending: { color: 'warning', label: 'Pending' },
    approved: { color: 'success', label: 'Approved' },
    rejected: { color: 'error', label: 'Rejected' },
    timedout: { color: 'default', label: 'Timed Out' },
  };
  const cfg = map[status] ?? { color: 'default' as const, label: status };
  return <Chip size="small" label={cfg.label} color={cfg.color} />;
}

function riskLevel(toolname: string): 'High' | 'Medium' | 'Low' {
  if (toolname.includes('shell') || toolname.includes('exec') || toolname.includes('delete')) return 'High';
  if (toolname.includes('write') || toolname.includes('run')) return 'Medium';
  return 'Low';
}

function riskChip(level: 'High' | 'Medium' | 'Low') {
  const map = { High: 'error', Medium: 'warning', Low: 'success' } as const;
  return <Chip size="small" label={level} color={map[level]} variant="outlined" />;
}

export default function ApprovalsPage() {
  const { data: approvals = [], isLoading, isError, error } = useAllApprovals();
  const approveRequest = useApproveRequest();
  const rejectRequest = useRejectRequest();

  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState<ApprovalStatus | ''>('');
  const [filterRisk, setFilterRisk] = useState<'' | 'High' | 'Medium' | 'Low'>('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const [detailOpen, setDetailOpen] = useState(false);
  const [detailTarget, setDetailTarget] = useState<ApprovalRequest | null>(null);

  const [actionOpen, setActionOpen] = useState(false);
  const [actionType, setActionType] = useState<'approve' | 'reject'>('approve');
  const [actionTarget, setActionTarget] = useState<ApprovalRequest | null>(null);
  const [comment, setComment] = useState('');

  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false, message: '', severity: 'success',
  });

  const notify = (message: string, severity: 'success' | 'error') =>
    setSnackbar({ open: true, message, severity });

  const filtered = useMemo(() => {
    let result = approvals;
    if (search) result = result.filter(a => a.toolname.toLowerCase().includes(search.toLowerCase()) || a.conversationid.toLowerCase().includes(search.toLowerCase()) || a.id.toLowerCase().includes(search.toLowerCase()));
    if (filterStatus) result = result.filter(a => a.status === filterStatus);
    if (filterRisk) result = result.filter(a => riskLevel(a.toolname) === filterRisk);
    return result;
  }, [approvals, search, filterStatus, filterRisk]);

  const paginated = filtered.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);

  function openAction(approval: ApprovalRequest, type: 'approve' | 'reject') {
    setActionTarget(approval);
    setActionType(type);
    setComment('');
    setActionOpen(true);
  }

  async function handleAction() {
    if (!actionTarget) return;
    try {
      const payload = { approver: 'admin', reason: comment || null };
      if (actionType === 'approve') {
        await approveRequest.mutateAsync({ approvalId: actionTarget.id, payload });
        notify('Request approved successfully.', 'success');
      } else {
        await rejectRequest.mutateAsync({ approvalId: actionTarget.id, payload });
        notify('Request rejected.', 'success');
      }
      setActionOpen(false);
    } catch (e) {
      notify(e instanceof Error ? e.message : 'Action failed.', 'error');
    }
  }

  const acting = approveRequest.isPending || rejectRequest.isPending;

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" fontWeight={700}>Approvals</Typography>
        <Typography variant="body1" color="text.secondary">Review pending human approval requests and their outcomes.</Typography>
      </Box>

      {isError && (
        <Alert severity="error">{error instanceof Error ? error.message : 'Failed to load approvals.'}</Alert>
      )}

      {/* Stats */}
      {!isLoading && (
        <Grid container spacing={2}>
          {(['pending', 'approved', 'rejected', 'timedout'] as ApprovalStatus[]).map(s => (
            <Grid item xs={6} sm={3} key={s}>
              <Paper variant="outlined" sx={{ p: 2, textAlign: 'center', cursor: 'pointer', bgcolor: filterStatus === s ? 'action.selected' : undefined }}
                onClick={() => setFilterStatus(v => v === s ? '' : s)}>
                <Typography variant="h5" fontWeight={700}>{approvals.filter(a => a.status === s).length}</Typography>
                <Typography variant="caption" color="text.secondary" textTransform="capitalize">{s}</Typography>
              </Paper>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Toolbar */}
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="flex-start">
        <TextField
          size="small" placeholder="Search by tool, ID, conversation…" value={search}
          onChange={e => { setSearch(e.target.value); setPage(0); }}
          InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> }}
          sx={{ minWidth: 260 }}
        />
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <InputLabel>Status</InputLabel>
          <Select value={filterStatus} label="Status" onChange={e => { setFilterStatus(e.target.value as ApprovalStatus | ''); setPage(0); }}>
            <MenuItem value="">All</MenuItem>
            <MenuItem value="pending">Pending</MenuItem>
            <MenuItem value="approved">Approved</MenuItem>
            <MenuItem value="rejected">Rejected</MenuItem>
            <MenuItem value="timedout">Timed Out</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 130 }}>
          <InputLabel>Risk Level</InputLabel>
          <Select value={filterRisk} label="Risk Level" onChange={e => { setFilterRisk(e.target.value as '' | 'High' | 'Medium' | 'Low'); setPage(0); }}>
            <MenuItem value="">All</MenuItem>
            <MenuItem value="High">High</MenuItem>
            <MenuItem value="Medium">Medium</MenuItem>
            <MenuItem value="Low">Low</MenuItem>
          </Select>
        </FormControl>
      </Stack>

      {isLoading ? (
        <Stack spacing={1}>
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} variant="rectangular" height={60} sx={{ borderRadius: 1 }} />)}
        </Stack>
      ) : filtered.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: 'center' }}>
          <HourglassEmptyIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
          <Typography variant="h6" gutterBottom>No approval requests</Typography>
          <Typography variant="body2" color="text.secondary">Requests requiring human review will appear here.</Typography>
        </Paper>
      ) : (
        <Paper variant="outlined">
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Request ID</TableCell>
                  <TableCell>Conversation</TableCell>
                  <TableCell>Tool</TableCell>
                  <TableCell>Risk</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Created</TableCell>
                  <TableCell>Expires</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {paginated.map(a => (
                  <TableRow key={a.id} hover>
                    <TableCell><Typography variant="caption" fontFamily="monospace">{a.id}</Typography></TableCell>
                    <TableCell><Typography variant="caption" fontFamily="monospace">{a.conversationid}</Typography></TableCell>
                    <TableCell><Typography variant="body2" fontWeight={600}>{a.toolname}</Typography></TableCell>
                    <TableCell>{riskChip(riskLevel(a.toolname))}</TableCell>
                    <TableCell>{statusChip(a.status)}</TableCell>
                    <TableCell><Typography variant="caption">{formatDate(a.createdat)}</Typography></TableCell>
                    <TableCell>
                      <Typography variant="caption" color={new Date(a.expiresat) < new Date() ? 'error' : 'text.secondary'}>
                        {formatDate(a.expiresat)}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Stack direction="row" justifyContent="flex-end" spacing={0.5}>
                        <Tooltip title="View Details">
                          <IconButton size="small" onClick={() => { setDetailTarget(a); setDetailOpen(true); }}>
                            <VisibilityIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        {a.status === 'pending' && (
                          <>
                            <Tooltip title="Approve">
                              <IconButton size="small" color="success" onClick={() => openAction(a, 'approve')}>
                                <CheckCircleIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title="Reject">
                              <IconButton size="small" color="error" onClick={() => openAction(a, 'reject')}>
                                <CancelIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          </>
                        )}
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          <TablePagination
            component="div" count={filtered.length} page={page} rowsPerPage={rowsPerPage}
            onPageChange={(_, p) => setPage(p)}
            onRowsPerPageChange={e => { setRowsPerPage(parseInt(e.target.value, 10)); setPage(0); }}
            rowsPerPageOptions={[5, 10, 25]}
          />
        </Paper>
      )}

      {/* Detail Dialog */}
      <Dialog open={detailOpen} onClose={() => setDetailOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Approval Request Details</DialogTitle>
        <DialogContent>
          {detailTarget && (
            <Stack spacing={2} sx={{ pt: 1 }}>
              <Box><Typography variant="caption" color="text.secondary">Request ID</Typography><Typography variant="body2" fontFamily="monospace">{detailTarget.id}</Typography></Box>
              <Box><Typography variant="caption" color="text.secondary">Tool</Typography><Typography variant="body2" fontWeight={600}>{detailTarget.toolname}</Typography></Box>
              <Box><Typography variant="caption" color="text.secondary">Conversation ID</Typography><Typography variant="body2" fontFamily="monospace">{detailTarget.conversationid}</Typography></Box>
              <Box><Typography variant="caption" color="text.secondary">Status</Typography><Box mt={0.5}>{statusChip(detailTarget.status)}</Box></Box>
              <Box><Typography variant="caption" color="text.secondary">Arguments</Typography>
                <Box component="pre" sx={{ mt: 0.5, p: 1.5, borderRadius: 1, bgcolor: 'grey.100', fontSize: 12, overflowX: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {JSON.stringify(detailTarget.arguments, null, 2)}
                </Box>
              </Box>
              {detailTarget.resolutionreason && <Box><Typography variant="caption" color="text.secondary">Resolution Reason</Typography><Typography variant="body2">{detailTarget.resolutionreason}</Typography></Box>}
              {detailTarget.resolvedby && <Box><Typography variant="caption" color="text.secondary">Resolved By</Typography><Typography variant="body2">{detailTarget.resolvedby}</Typography></Box>}
            </Stack>
          )}
        </DialogContent>
        <DialogActions><Button onClick={() => setDetailOpen(false)}>Close</Button></DialogActions>
      </Dialog>

      {/* Approve/Reject Dialog */}
      <Dialog open={actionOpen} onClose={() => setActionOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>{actionType === 'approve' ? 'Approve Request?' : 'Reject Request?'}</DialogTitle>
        <DialogContent>
          <DialogContentText mb={2}>
            {actionType === 'approve'
              ? `Approve tool call "${actionTarget?.toolname}" for conversation ${actionTarget?.conversationid}?`
              : `Reject and block tool call "${actionTarget?.toolname}" for conversation ${actionTarget?.conversationid}?`}
          </DialogContentText>
          <TextField label="Comment (optional)" value={comment} onChange={e => setComment(e.target.value)} fullWidth multiline rows={2} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setActionOpen(false)}>Cancel</Button>
          <Button variant="contained" color={actionType === 'approve' ? 'success' : 'error'} onClick={handleAction} disabled={acting}>
            {acting ? 'Processing…' : actionType === 'approve' ? 'Approve' : 'Reject'}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={snackbar.open} autoHideDuration={4000} onClose={() => setSnackbar(s => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar(s => ({ ...s, open: false }))}>{snackbar.message}</Alert>
      </Snackbar>
    </Stack>
  );
}
