import { Box, AppBar, Button, Toolbar, Typography } from '@mui/material'

export type TopBarProps = {
  backendStatusLabel?: string
}

export default function TopBar({ backendStatusLabel = 'Backend status: placeholder' }: TopBarProps) {
  return (
    <AppBar
      position="sticky"
      color="inherit"
      sx={{
        borderBottom: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
      }}
    >
      <Toolbar sx={{ gap: 2, justifyContent: 'space-between' }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h6" fontWeight={700} noWrap>
            ArmorIQ Policy Admin
          </Typography>
          <Typography variant="body2" color="text.secondary" noWrap>
            Security controls, approvals, budgets, logs, and chat
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Box
            sx={{
              px: 1.5,
              py: 0.75,
              borderRadius: 999,
              bgcolor: 'success.50',
              color: 'success.dark',
              border: 1,
              borderColor: 'success.200',
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {backendStatusLabel}
          </Box>
          <Button variant="text" color="inherit">
            User menu
          </Button>
        </Box>
      </Toolbar>
    </AppBar>
  )
}
