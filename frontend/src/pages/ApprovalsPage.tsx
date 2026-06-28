import { Box, Typography } from '@mui/material'

export default function ApprovalsPage() {
  return (
    <Box sx={{ display: 'grid', gap: 1.5 }}>
      <Typography variant="h4" fontWeight={700}>
        Approvals
      </Typography>
      <Typography variant="body1" color="text.secondary">
        Review pending human approval requests and their outcomes.
      </Typography>
      <Typography variant="h6" sx={{ mt: 2 }}>
        Coming Soon
      </Typography>
    </Box>
  )
}