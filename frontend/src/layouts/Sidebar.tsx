import { useMemo } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  Box,
  Chip,
  CircularProgress,
  Divider,
  List,
  ListItemButton,
  ListItemText,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import ErrorIcon from '@mui/icons-material/Error'

import { defaultRoutePath, navigationItems } from '../routes/navigation'
import { useHealth } from '../hooks/useHealth'

export type SidebarProps = {
  onNavigate?: () => void
}

export default function Sidebar({ onNavigate }: SidebarProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const { data: health, isLoading: healthLoading, isError: healthError } = useHealth()

  const activePath = useMemo(() => {
    const current = navigationItems.find((item) => item.path === location.pathname)
    return current?.path ?? defaultRoutePath
  }, [location.pathname])

  const statusLabel = healthLoading
    ? 'Checking...'
    : healthError
    ? 'Offline'
    : health?.status === 'ok'
    ? 'Online'
    : 'Unknown'

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Toolbar sx={{ px: 3, py: 2, alignItems: 'flex-start' }}>
        <Box>
          <Typography variant="h6" fontWeight={700} lineHeight={1.1}>
            ArmorIQ
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Policy Admin Console
          </Typography>
        </Box>
      </Toolbar>
      <Divider />
      <List sx={{ px: 1, py: 1, flex: 1 }}>
        {navigationItems.map((item) => {
          const selected = activePath === item.path
          return (
            <ListItemButton
              key={item.path}
              selected={selected}
              onClick={() => {
                navigate(item.path)
                onNavigate?.()
              }}
              sx={{
                borderRadius: 2,
                mb: 0.5,
                mx: 0.5,
                '&.Mui-selected': {
                  bgcolor: 'primary.main',
                  color: 'primary.contrastText',
                  '&:hover': {
                    bgcolor: 'primary.dark',
                  },
                },
              }}
            >
              <ListItemText
                primary={item.label}
                primaryTypographyProps={{ fontWeight: selected ? 700 : 500 }}
              />
              {item.path === '/approvals' && (health?.pending_approvals ?? 0) > 0 && (
                <Chip
                  label={health!.pending_approvals}
                  size="small"
                  color="warning"
                  sx={{ height: 18, fontSize: 11 }}
                />
              )}
            </ListItemButton>
          )
        })}
      </List>
      <Box sx={{ p: 2 }}>
        <Box
          sx={{
            border: 1,
            borderColor: 'divider',
            borderRadius: 2,
            p: 1.5,
            bgcolor: 'background.paper',
          }}
        >
          <Typography variant="caption" color="text.secondary" display="block" mb={0.5}>
            Backend Status
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
            {healthLoading ? (
              <CircularProgress size={14} />
            ) : healthError ? (
              <ErrorIcon sx={{ fontSize: 16, color: 'error.main' }} />
            ) : (
              <CheckCircleIcon sx={{ fontSize: 16, color: 'success.main' }} />
            )}
            <Typography variant="body2" fontWeight={600}>
              {statusLabel}
            </Typography>
          </Box>
          {health && (
            <Tooltip title="Rules / Pending approvals">
              <Typography variant="caption" color="text.disabled" sx={{ mt: 0.25, display: 'block' }}>
                {health.rules} rules · {health.pending_approvals} pending
              </Typography>
            </Tooltip>
          )}
        </Box>
      </Box>
    </Box>
  )
}
