import { useState, useMemo, useCallback } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Collapse,
  FormControl,
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
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import RefreshIcon from '@mui/icons-material/Refresh';
import DownloadIcon from '@mui/icons-material/Download';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import SearchIcon from '@mui/icons-material/Search';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';

import { useLogs } from '../hooks/useLogs';
import type { LogEntry } from '../types/logs';

function formatDate(iso: string) {
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function outcomeColor(outcome: string): 'success' | 'warning' | 'error' | 'default' {
  switch (outcome) {
    case 'allowed': return 'success';
    case 'requires_approval': return 'warning';
    case 'denied': return 'error';
    default: return 'default';
  }
}

function ExpandedRow({ log }: { log: LogEntry }) {
  return (
    <Box sx={{ p: 2, bgcolor: 'background.default' }}>
      <Stack spacing={2} direction={{ xs: 'column', md: 'row' }}>
        <Box flex={1}>
          <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.5}>Arguments</Typography>
          <Box component="pre" sx={{ m: 0, p: 1.5, borderRadius: 1, bgcolor: 'grey.100', fontSize: 12, overflowX: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {JSON.stringify(log.arguments, null, 2)}
          </Box>
        </Box>
        {log.rewrittenarguments && (
          <Box flex={1}>
            <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.5}>Rewritten Arguments</Typography>
            <Box component="pre" sx={{ m: 0, p: 1.5, borderRadius: 1, bgcolor: 'grey.100', fontSize: 12, overflowX: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {JSON.stringify(log.rewrittenarguments, null, 2)}
            </Box>
          </Box>
        )}
        <Box flex={1}>
          <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.5}>Meta</Typography>
          <Stack spacing={0.5}>
            {log.matchedruleid && <Typography variant="caption">Matched Rule: <code>{log.matchedruleid}</code></Typography>}
            {log.reason && <Typography variant="caption">Reason: {log.reason}</Typography>}
            {log.enginefailure && <Chip size="small" label="Engine Failure" color="error" variant="outlined" />}
          </Stack>
        </Box>
      </Stack>
    </Box>
  );
}

function LogRow({ log, onCopy }: { log: LogEntry; onCopy: (log: LogEntry) => void }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <TableRow hover sx={{ '& > *': { borderBottom: expanded ? 'unset' : undefined } }}>
        <TableCell padding="checkbox">
          <IconButton size="small" onClick={() => setExpanded((value) => !value)}>
            {expanded ? <KeyboardArrowUpIcon fontSize="small" /> : <KeyboardArrowDownIcon fontSize="small" />}
          </IconButton>
        </TableCell>
        <TableCell><Typography variant="caption">{formatDate(log.timestamp)}</Typography></TableCell>
        <TableCell><Typography variant="caption" fontFamily="monospace">{log.conversationid}</Typography></TableCell>
        <TableCell><Typography variant="body2" fontWeight={600}>{log.toolname}</Typography></TableCell>
        <TableCell><Chip size="small" label={log.outcome} color={outcomeColor(log.outcome)} /></TableCell>
        <TableCell><Typography variant="caption">{log.executiontimems.toFixed(1)} ms</Typography></TableCell>
        <TableCell>
          <Typography variant="caption" color="text.secondary" sx={{ maxWidth: 220, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {log.reason ?? '—'}
          </Typography>
        </TableCell>
        <TableCell align="right">
          <Tooltip title="Copy log entry">
            <IconButton size="small" onClick={() => onCopy(log)}><ContentCopyIcon fontSize="small" /></IconButton>
          </Tooltip>
        </TableCell>
      </TableRow>
      <TableRow>
        <TableCell colSpan={8} sx={{ p: 0 }}>
          <Collapse in={expanded} unmountOnExit>
            <ExpandedRow log={log} />
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
}

export default function LogsPage() {
  const { data: logs = [], isLoading, isError, error, refetch, isFetching } = useLogs();

  const [search, setSearch] = useState('');
  const [filterOutcome, setFilterOutcome] = useState('');
  const [filterTool, setFilterTool] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string }>({
    open: false, message: '',
  });

  const toolOptions = useMemo(() => [...new Set(logs.map((log) => log.toolname))], [logs]);

  const filtered = useMemo(() => {
    let result = logs;
    if (search) result = result.filter((log) => log.toolname.toLowerCase().includes(search.toLowerCase()) || log.conversationid.toLowerCase().includes(search.toLowerCase()) || (log.reason ?? '').toLowerCase().includes(search.toLowerCase()));
    if (filterOutcome) result = result.filter((log) => log.outcome === filterOutcome);
    if (filterTool) result = result.filter((log) => log.toolname === filterTool);
    if (dateFrom) result = result.filter((log) => new Date(log.timestamp) >= new Date(dateFrom));
    if (dateTo) result = result.filter((log) => new Date(log.timestamp) <= new Date(dateTo + 'T23:59:59'));
    return [...result].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  }, [logs, search, filterOutcome, filterTool, dateFrom, dateTo]);

  const paginated = filtered.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);

  const handleCopy = useCallback((log: LogEntry) => {
    const text = JSON.stringify(log, null, 2);
    navigator.clipboard.writeText(text).then(() => {
      setSnackbar({ open: true, message: 'Log entry copied to clipboard.' });
    });
  }, []);

  function exportCsv() {
    const headers = ['timestamp', 'conversationid', 'toolname', 'outcome', 'executiontimems', 'reason', 'matchedruleid', 'enginefailure'];
    const rows = filtered.map((log) => headers.map((header) => {
      const value = (log as Record<string, unknown>)[header];
      if (value === null || value === undefined) return '';
      const stringValue = String(value);
      return stringValue.includes(',') ? `"${stringValue}"` : stringValue;
    }).join(','));
    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const anchor = document.createElement('a');
    anchor.href = URL.createObjectURL(blob);
    anchor.download = `armoriq-logs-${new Date().toISOString().slice(0, 10)}.csv`;
    anchor.click();
  }

  return (
    <Stack spacing={3}>
      <Stack direction="row" alignItems="flex-start" justifyContent="space-between" flexWrap="wrap" gap={1}>
        <Box>
          <Typography variant="h4" fontWeight={700}>Logs</Typography>
          <Typography variant="body1" color="text.secondary">Audit trail for policy decisions and tool actions.</Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" startIcon={<DownloadIcon />} onClick={exportCsv} disabled={filtered.length === 0}>Export CSV</Button>
          <Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => refetch()} disabled={isFetching}>
            {isFetching ? 'Refreshing…' : 'Refresh · auto 30s'}
          </Button>
        </Stack>
      </Stack>

      {isError && (
        <Alert severity="error">{error instanceof Error ? error.message : 'Failed to load logs.'}</Alert>
      )}

      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="flex-start" flexWrap="wrap">
        <TextField
          size="small"
          placeholder="Search logs…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
          InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> }}
          sx={{ minWidth: 220 }}
        />
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Outcome</InputLabel>
          <Select value={filterOutcome} label="Outcome" onChange={(e) => { setFilterOutcome(e.target.value); setPage(0); }}>
            <MenuItem value="">All</MenuItem>
            <MenuItem value="allowed">Allowed</MenuItem>
            <MenuItem value="denied">Denied</MenuItem>
            <MenuItem value="requires_approval">Requires Approval</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Tool</InputLabel>
          <Select value={filterTool} label="Tool" onChange={(e) => { setFilterTool(e.target.value); setPage(0); }}>
            <MenuItem value="">All tools</MenuItem>
            {toolOptions.map((tool) => <MenuItem key={tool} value={tool}>{tool}</MenuItem>)}
          </Select>
        </FormControl>
        <TextField
          size="small"
          label="From"
          type="date"
          value={dateFrom}
          onChange={(e) => {
            setDateFrom(e.target.value);
            setPage(0);
          }}
          InputLabelProps={{ shrink: true }}
        />
        <TextField
          size="small"
          label="To"
          type="date"
          value={dateTo}
          onChange={(e) => {
            setDateTo(e.target.value);
            setPage(0);
          }}
          InputLabelProps={{ shrink: true }}
        />
      </Stack>

      {isLoading ? (
        <Stack spacing={1}>
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} variant="rectangular" height={54} sx={{ borderRadius: 1 }} />)}
        </Stack>
      ) : filtered.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: 'center' }}>
          <ReceiptLongIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
          <Typography variant="h6" gutterBottom>No logs found</Typography>
          <Typography variant="body2" color="text.secondary">Audit records will appear here as tools are executed.</Typography>
        </Paper>
      ) : (
        <Paper variant="outlined">
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell />
                  <TableCell>Timestamp</TableCell>
                  <TableCell>Conversation</TableCell>
                  <TableCell>Tool</TableCell>
                  <TableCell>Result</TableCell>
                  <TableCell>Duration</TableCell>
                  <TableCell>Reason</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {paginated.map((log, index) => (
                  <LogRow key={`${log.timestamp}-${log.conversationid}-${log.toolname}-${index}`} log={log} onCopy={handleCopy} />
                ))}
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
            rowsPerPageOptions={[10, 25, 50]}
          />
        </Paper>
      )}

      <Snackbar
        open={snackbar.open}
        autoHideDuration={3000}
        onClose={() => setSnackbar((state) => ({ ...state, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert severity="success" onClose={() => setSnackbar((state) => ({ ...state, open: false }))}>{snackbar.message}</Alert>
      </Snackbar>
    </Stack>
  );
}
