import { useState, useMemo } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Autocomplete,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
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
  Switch,
  ToggleButton,
  ToggleButtonGroup,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TableSortLabel,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import SearchIcon from '@mui/icons-material/Search';
import GavelIcon from '@mui/icons-material/Gavel';

import { useCreateRule, useDeleteRule, useRules, useUpdateRule } from '../hooks/useRules';
import { useTools } from '../hooks/useTools';
import type { RuleAction, RuleCreate, RuleResponse, RuleScope, RuleType } from '../types/rules';
import type { ToolResponse } from '../types/tools';

function formatDate(iso: string) {
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function actionChip(action: RuleAction) {
  const map: Record<RuleAction, { color: 'success' | 'error' | 'warning'; label: string }> = {
    allow: { color: 'success', label: 'Allow' },
    block: { color: 'error', label: 'Deny' },
    require_approval: { color: 'warning', label: 'Require Approval' },
  };
  const cfg = map[action] ?? { color: 'default' as const, label: action };
  return <Chip size="small" label={cfg.label} color={cfg.color} />;
}

const DEFAULT_FORM: RuleCreate = {
  name: '',
  action: 'allow',
  toolpattern: '',
  ruletype: 'exact',
  priority: 5,
  enabled: true,
  constraints: [],
  approvaltimeoutseconds: 60,
  reason: null,
  description: null,
  scope: 'global',
  scopeid: null,
};

type Order = 'asc' | 'desc';
type ToolMode = 'existing' | 'pattern';

type ToolOption = ToolResponse;

function isKnownTool(tool: string, tools: ToolOption[]) {
  return tools.some(option => option.name === tool);
}

export default function RulesPage() {
  const { data: rules = [], isLoading, isError, error } = useRules();
  const { data: tools = [], isLoading: toolsLoading, isError: toolsError } = useTools();
  const createRule = useCreateRule();
  const updateRule = useUpdateRule();
  const deleteRule = useDeleteRule();

  const [search, setSearch] = useState('');
  const [filterTool, setFilterTool] = useState('');
  const [filterStatus, setFilterStatus] = useState<'' | 'enabled' | 'disabled'>('');
  const [order, setOrder] = useState<Order>('asc');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const [editOpen, setEditOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<RuleResponse | null>(null);
  const [form, setForm] = useState<RuleCreate>(DEFAULT_FORM);
  const [toolMode, setToolMode] = useState<ToolMode>('existing');

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<RuleResponse | null>(null);

  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false, message: '', severity: 'success',
  });

  const ruleToolPatterns = useMemo(() => [...new Set(rules.map(r => r.toolpattern))], [rules]);
  const toolOptions = useMemo(() => {
    if (tools.length > 0) return tools;
    return ruleToolPatterns.map(name => ({ name, description: null, server_name: 'policy-rules' }));
  }, [tools, ruleToolPatterns]);

  const filtered = useMemo(() => {
    let result = rules;
    if (search) result = result.filter(r => r.name.toLowerCase().includes(search.toLowerCase()) || r.toolpattern.toLowerCase().includes(search.toLowerCase()));
    if (filterTool) result = result.filter(r => r.toolpattern === filterTool);
    if (filterStatus === 'enabled') result = result.filter(r => r.enabled);
    if (filterStatus === 'disabled') result = result.filter(r => !r.enabled);
    result = [...result].sort((a, b) => order === 'asc' ? a.priority - b.priority : b.priority - a.priority);
    return result;
  }, [rules, search, filterTool, filterStatus, order]);

  const paginated = filtered.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);

  const notify = (message: string, severity: 'success' | 'error') =>
    setSnackbar({ open: true, message, severity });

  function openAdd() {
    setEditTarget(null);
    setForm(DEFAULT_FORM);
    setToolMode('existing');
    setEditOpen(true);
  }

  function openEdit(rule: RuleResponse) {
    setEditTarget(rule);
    setToolMode(rule.ruletype === 'exact' && isKnownTool(rule.toolpattern, toolOptions) ? 'existing' : 'pattern');
    setForm({
      name: rule.name, action: rule.action, toolpattern: rule.toolpattern,
      ruletype: rule.ruletype, priority: rule.priority, enabled: rule.enabled,
      constraints: rule.constraints, approvaltimeoutseconds: rule.approvaltimeoutseconds,
      reason: rule.reason, description: rule.description, scope: rule.scope, scopeid: rule.scopeid,
    });
    setEditOpen(true);
  }

  async function handleSave() {
    try {
      if (editTarget) {
        await updateRule.mutateAsync({ ruleId: editTarget.id, payload: form });
        notify('Rule updated successfully.', 'success');
      } else {
        await createRule.mutateAsync(form);
        notify('Rule created successfully.', 'success');
      }
      setEditOpen(false);
    } catch (e) {
      notify(e instanceof Error ? e.message : 'Operation failed.', 'error');
    }
  }

  async function handleToggle(rule: RuleResponse) {
    try {
      await updateRule.mutateAsync({
        ruleId: rule.id,
        payload: { name: rule.name, action: rule.action, toolpattern: rule.toolpattern, ruletype: rule.ruletype, priority: rule.priority, enabled: !rule.enabled, constraints: rule.constraints, approvaltimeoutseconds: rule.approvaltimeoutseconds, reason: rule.reason, description: rule.description, scope: rule.scope, scopeid: rule.scopeid },
      });
      notify(`Rule ${!rule.enabled ? 'enabled' : 'disabled'}.`, 'success');
    } catch {
      notify('Failed to toggle rule.', 'error');
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await deleteRule.mutateAsync(deleteTarget.id);
      notify('Rule deleted.', 'success');
      setDeleteOpen(false);
      setDeleteTarget(null);
    } catch {
      notify('Failed to delete rule.', 'error');
    }
  }

  const saving = createRule.isPending || updateRule.isPending;
  const toolDescription = toolMode === 'existing'
    ? 'Choose from registered MCP tools discovered from the backend.'
    : 'Use patterns for enterprise rules, such as glob or regex matching.';

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" fontWeight={700}>Rules</Typography>
        <Typography variant="body1" color="text.secondary">Create, review, and manage policy rules for tool control.</Typography>
      </Box>

      {isError && (
        <Alert severity="error">{error instanceof Error ? error.message : 'Failed to load rules.'}</Alert>
      )}

      {toolsError && (
        <Alert severity="warning">
          Tool discovery is unavailable right now. Existing tool names will be inferred from saved rules.
        </Alert>
      )}

      {/* Toolbar */}
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="flex-start">
        <TextField
          size="small" placeholder="Search rules…" value={search}
          onChange={e => { setSearch(e.target.value); setPage(0); }}
          InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> }}
          sx={{ minWidth: 220 }}
        />
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Tool</InputLabel>
          <Select value={filterTool} label="Tool" onChange={e => { setFilterTool(e.target.value); setPage(0); }}>
            <MenuItem value="">All tools</MenuItem>
            {toolOptions.map(t => <MenuItem key={t.name} value={t.name}>{t.name}</MenuItem>)}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <InputLabel>Status</InputLabel>
          <Select value={filterStatus} label="Status" onChange={e => { setFilterStatus(e.target.value as '' | 'enabled' | 'disabled'); setPage(0); }}>
            <MenuItem value="">All</MenuItem>
            <MenuItem value="enabled">Enabled</MenuItem>
            <MenuItem value="disabled">Disabled</MenuItem>
          </Select>
        </FormControl>
        <Box sx={{ flexGrow: 1 }} />
        <Button variant="contained" startIcon={<AddIcon />} onClick={openAdd}>Add Rule</Button>
      </Stack>

      {/* Table */}
      {isLoading ? (
        <Stack spacing={1}>
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} variant="rectangular" height={52} sx={{ borderRadius: 1 }} />)}
        </Stack>
      ) : filtered.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: 'center' }}>
          <GavelIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
          <Typography variant="h6" gutterBottom>No rules found</Typography>
          <Typography variant="body2" color="text.secondary" mb={3}>Create your first policy rule to start controlling tool access.</Typography>
          <Button variant="contained" startIcon={<AddIcon />} onClick={openAdd}>Add Rule</Button>
        </Paper>
      ) : (
        <Paper variant="outlined">
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Rule Name</TableCell>
                  <TableCell>Tool Pattern</TableCell>
                  <TableCell>Action</TableCell>
                  <TableCell>Condition</TableCell>
                  <TableCell sortDirection={order}>
                    <TableSortLabel active direction={order} onClick={() => setOrder(o => o === 'asc' ? 'desc' : 'asc')}>
                      Priority
                    </TableSortLabel>
                  </TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Created At</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {paginated.map(rule => (
                  <TableRow key={rule.id} hover>
                    <TableCell>
                      <Typography variant="body2" fontWeight={600}>{rule.name}</Typography>
                      {rule.description && <Typography variant="caption" color="text.secondary">{rule.description}</Typography>}
                    </TableCell>
                    <TableCell><Typography variant="body2" fontFamily="monospace">{rule.toolpattern}</Typography></TableCell>
                    <TableCell>{actionChip(rule.action)}</TableCell>
                    <TableCell><Typography variant="caption" color="text.secondary">{rule.ruletype}</Typography></TableCell>
                    <TableCell><Chip size="small" label={rule.priority} variant="outlined" /></TableCell>
                    <TableCell>
                      <Tooltip title={rule.enabled ? 'Disable rule' : 'Enable rule'}>
                        <Switch size="small" checked={rule.enabled} onChange={() => handleToggle(rule)} />
                      </Tooltip>
                    </TableCell>
                    <TableCell><Typography variant="caption">{formatDate(rule.createdat)}</Typography></TableCell>
                    <TableCell align="right">
                      <Stack direction="row" justifyContent="flex-end">
                        <Tooltip title="Edit"><IconButton size="small" onClick={() => openEdit(rule)}><EditIcon fontSize="small" /></IconButton></Tooltip>
                        <Tooltip title="Delete"><IconButton size="small" color="error" onClick={() => { setDeleteTarget(rule); setDeleteOpen(true); }}><DeleteIcon fontSize="small" /></IconButton></Tooltip>
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

      {/* Add/Edit Dialog */}
      <Dialog open={editOpen} onClose={() => setEditOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editTarget ? 'Edit Rule' : 'Add Rule'}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField label="Rule Name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} fullWidth required />
            <Stack spacing={1}>
              <ToggleButtonGroup
                size="small"
                exclusive
                value={toolMode}
                onChange={(_, value: ToolMode | null) => value && setToolMode(value)}
              >
                <ToggleButton value="existing">Select Existing Tool</ToggleButton>
                <ToggleButton value="pattern">Pattern</ToggleButton>
              </ToggleButtonGroup>
              <Typography variant="caption" color="text.secondary">
                {toolDescription}
              </Typography>
            </Stack>
            {toolMode === 'existing' ? (
              <Autocomplete
                options={toolOptions}
                loading={toolsLoading}
                value={toolOptions.find(tool => tool.name === form.toolpattern) ?? null}
                isOptionEqualToValue={(option, value) => option.name === value.name}
                getOptionLabel={(option) => option.name}
                onChange={(_, value) => setForm(f => ({ ...f, toolpattern: value?.name ?? '', ruletype: 'exact' }))}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Tool"
                    placeholder="Search registered tools"
                    helperText="Select a discovered MCP tool to avoid typos."
                    required
                  />
                )}
                renderOption={(props, option) => (
                  <li {...props} key={option.name}>
                    <Box>
                      <Typography variant="body2" fontWeight={600}>{option.name}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {option.description ?? `Source: ${option.server_name}`}
                      </Typography>
                    </Box>
                  </li>
                )}
              />
            ) : (
              <TextField
                label="Tool Pattern"
                value={form.toolpattern}
                onChange={e => setForm(f => ({ ...f, toolpattern: e.target.value }))}
                fullWidth
                required
                helperText="Examples: github_*, finance.*, or ^send_.*$"
              />
            )}
            <Stack direction="row" spacing={2}>
              <FormControl fullWidth>
                <InputLabel>Action</InputLabel>
                <Select label="Action" value={form.action} onChange={e => setForm(f => ({ ...f, action: e.target.value as RuleAction }))}>
                  <MenuItem value="allow">Allow</MenuItem>
                  <MenuItem value="block">Deny</MenuItem>
                  <MenuItem value="require_approval">Require Approval</MenuItem>
                </Select>
              </FormControl>
              <FormControl fullWidth>
                <InputLabel>Type</InputLabel>
                <Select label="Type" value={form.ruletype} onChange={e => setForm(f => ({ ...f, ruletype: e.target.value as RuleType }))}>
                  <MenuItem value="exact">Exact</MenuItem>
                  <MenuItem value="glob">Glob</MenuItem>
                  <MenuItem value="regex">Regex</MenuItem>
                </Select>
              </FormControl>
            </Stack>
            <Stack direction="row" spacing={2}>
              <TextField label="Priority" type="number" value={form.priority} onChange={e => setForm(f => ({ ...f, priority: parseInt(e.target.value, 10) || 1 }))} fullWidth inputProps={{ min: 1, max: 100 }} />
              <FormControl fullWidth>
                <InputLabel>Scope</InputLabel>
                <Select label="Scope" value={form.scope} onChange={e => setForm(f => ({ ...f, scope: e.target.value as RuleScope }))}>
                  <MenuItem value="global">Global</MenuItem>
                  <MenuItem value="conversation">Conversation</MenuItem>
                </Select>
              </FormControl>
            </Stack>
            <TextField label="Description (optional)" value={form.description ?? ''} onChange={e => setForm(f => ({ ...f, description: e.target.value || null }))} fullWidth multiline rows={2} />
            <TextField label="Reason (optional)" value={form.reason ?? ''} onChange={e => setForm(f => ({ ...f, reason: e.target.value || null }))} fullWidth />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleSave} disabled={saving || !form.name || !form.toolpattern}>
            {saving ? 'Saving…' : editTarget ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirm */}
      <Dialog open={deleteOpen} onClose={() => setDeleteOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Delete Rule?</DialogTitle>
        <DialogContent>
          <DialogContentText>Are you sure you want to delete <strong>{deleteTarget?.name}</strong>? This cannot be undone.</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteOpen(false)}>Cancel</Button>
          <Button variant="contained" color="error" onClick={handleDelete} disabled={deleteRule.isPending}>
            {deleteRule.isPending ? 'Deleting…' : 'Delete'}
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
