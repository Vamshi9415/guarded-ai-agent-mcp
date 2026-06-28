import { Box, Typography } from '@mui/material'

export default function RulesPage() {
  return (
    <Box sx={{ display: 'grid', gap: 1.5 }}>
      <Typography variant="h4" fontWeight={700}>
        Rules
      </Typography>
      <Typography variant="body1" color="text.secondary">
        Create, review, and manage policy rules for tool control.
      </Typography>
      <Typography variant="h6" sx={{ mt: 2 }}>
        Coming Soon
      </Typography>
    </Box>
  )
}