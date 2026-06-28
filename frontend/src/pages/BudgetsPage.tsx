import { Box, Typography } from '@mui/material'

export default function BudgetsPage() {
  return (
    <Box sx={{ display: 'grid', gap: 1.5 }}>
      <Typography variant="h4" fontWeight={700}>
        Budgets
      </Typography>
      <Typography variant="body1" color="text.secondary">
        Inspect and adjust conversation token budgets.
      </Typography>
      <Typography variant="h6" sx={{ mt: 2 }}>
        Coming Soon
      </Typography>
    </Box>
  )
}