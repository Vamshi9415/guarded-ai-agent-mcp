import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  Divider,
  Grid,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  Stack,
  Typography,
} from '@mui/material'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'
import GavelIcon from '@mui/icons-material/Gavel'
import PendingActionsIcon from '@mui/icons-material/PendingActions'
import ShieldIcon from '@mui/icons-material/Shield'
import AutorenewIcon from '@mui/icons-material/Autorenew'

import { useHealth } from '../hooks/useHealth'

function formatTimestamp(value: number | undefined) {
  if (!value) return 'Not yet loaded'
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    month: 'short',
    day: 'numeric',
  }).format(new Date(value))
}

type MetricCardProps = {
  title: string
  value: string | number
  helper: string
  icon: React.ReactNode
  accent?: 'primary' | 'success' | 'warning' | 'error'
}

function MetricCard({ title, value, helper, icon, accent = 'primary' }: MetricCardProps) {
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Stack spacing={2}>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="overline" sx={{ letterSpacing: 1, color: 'text.secondary' }}>
              {title}
            </Typography>
            <Box
              sx={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 40,
                height: 40,
                borderRadius: 2,
                bgcolor: `${accent}.main`,
                color: `${accent}.contrastText`,
              }}
            >
              {icon}
            </Box>
          </Stack>
          <Typography variant="h4" fontWeight={700}>
            {value}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {helper}
          </Typography>
        </Stack>
      </CardContent>
    </Card>
  )
}

export default function DashboardPage() {
  const {
    data: health,
    isLoading,
    isFetching,
    isError,
    error,
    dataUpdatedAt,
  } = useHealth()

  const backendOnline = health?.status === 'ok'
  const pendingApprovals = health?.pending_approvals ?? 0
  const ruleCount = health?.rules ?? 0

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" fontWeight={700} gutterBottom>
          Dashboard
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Operational snapshot for the ArmorIQ backend, approval queue, and policy coverage.
        </Typography>
      </Box>

      {isFetching ? <LinearProgress sx={{ borderRadius: 999 }} /> : null}

      {isError ? (
        <Alert severity="error" icon={<ErrorOutlineIcon fontSize="inherit" />}>
          {error instanceof Error
            ? `Unable to load backend health: ${error.message}`
            : 'Unable to load backend health.'}
        </Alert>
      ) : null}

      <Grid container spacing={3}>
        <Grid item xs={12} sm={6} lg={3}>
          <MetricCard
            title="Backend"
            value={isLoading ? 'Loading…' : backendOnline ? 'Online' : 'Offline'}
            helper="Live status from the FastAPI health endpoint."
            icon={backendOnline ? <CheckCircleIcon /> : <ShieldIcon />}
            accent={backendOnline ? 'success' : 'error'}
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <MetricCard
            title="Policy rules"
            value={isLoading ? '—' : ruleCount}
            helper="Number of rules currently loaded into the policy store."
            icon={<GavelIcon />}
            accent="primary"
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <MetricCard
            title="Pending approvals"
            value={isLoading ? '—' : pendingApprovals}
            helper="Requests that still require a human decision."
            icon={<PendingActionsIcon />}
            accent={pendingApprovals > 0 ? 'warning' : 'success'}
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <MetricCard
            title="Last refresh"
            value={formatTimestamp(dataUpdatedAt)}
            helper="React Query refreshes this snapshot every 30 seconds."
            icon={<AutorenewIcon />}
            accent="primary"
          />
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid item xs={12} lg={7}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Stack spacing={2}>
                <Typography variant="h6" fontWeight={700}>
                  Service summary
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  This page stays intentionally thin and reads live state from the backend rather than recreating policy logic in the UI.
                </Typography>
                <Divider />
                <List disablePadding>
                  <ListItem disableGutters>
                    <ListItemText
                      primary="API health"
                      secondary={
                        isLoading
                          ? 'Checking backend reachability.'
                          : backendOnline
                            ? 'Backend is reachable and reporting status ok.'
                            : 'Backend is unavailable or reporting a non-ok status.'
                      }
                    />
                  </ListItem>
                  <Divider component="li" />
                  <ListItem disableGutters>
                    <ListItemText
                      primary="Rules loaded"
                      secondary={
                        isLoading
                          ? 'Waiting for rule inventory.'
                          : `${ruleCount} rule${ruleCount === 1 ? '' : 's'} available for evaluation.`
                      }
                    />
                  </ListItem>
                  <Divider component="li" />
                  <ListItem disableGutters>
                    <ListItemText
                      primary="Approval queue"
                      secondary={
                        isLoading
                          ? 'Waiting for approval queue size.'
                          : pendingApprovals > 0
                            ? `${pendingApprovals} item${pendingApprovals === 1 ? '' : 's'} currently waiting for review.`
                            : 'No pending approvals right now.'
                      }
                    />
                  </ListItem>
                </List>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={5}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Stack spacing={2}>
                <Typography variant="h6" fontWeight={700}>
                  Suggested next actions
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Use this view as the control-plane overview, then drill into the workflow pages that need attention.
                </Typography>
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                  <Chip label="Review Approvals" color={pendingApprovals > 0 ? 'warning' : 'default'} variant={pendingApprovals > 0 ? 'filled' : 'outlined'} />
                  <Chip label="Tune Rules" color="primary" variant="outlined" />
                  <Chip label="Inspect Logs" variant="outlined" />
                </Stack>
                <Divider />
                <Box>
                  <Typography variant="subtitle2" gutterBottom>
                    Status guidance
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    If approvals rise above zero, the approvals queue is your first stop. If backend health is not ok, treat this as an operational incident before making policy changes.
                  </Typography>
                </Box>
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Stack>
  )
}