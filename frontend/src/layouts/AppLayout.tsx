import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Box, Drawer, Toolbar, useMediaQuery, useTheme } from '@mui/material'

import Sidebar from './Sidebar'
import TopBar from './TopBar'

const drawerWidth = 280
const topBarHeight = 64

export default function AppLayout() {
  const theme = useTheme()
  const isDesktop = useMediaQuery(theme.breakpoints.up('md'))
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <TopBar backendStatusLabel="Backend status: placeholder" />

      <Box sx={{ display: 'flex', minHeight: `calc(100vh - ${topBarHeight}px)` }}>
        <Box
          component="nav"
          aria-label="primary navigation"
          sx={{ width: { md: drawerWidth }, flexShrink: { md: 0 } }}
        >
          <Drawer
            variant={isDesktop ? 'permanent' : 'temporary'}
            open={isDesktop || mobileOpen}
            onClose={() => setMobileOpen(false)}
            ModalProps={{ keepMounted: true }}
            anchor="left"
            sx={{
              width: drawerWidth,
              '& .MuiDrawer-paper': {
                width: drawerWidth,
                boxSizing: 'border-box',
                borderRight: 1,
                borderColor: 'divider',
                bgcolor: 'background.paper',
                top: { md: `${topBarHeight}px` },
                height: { md: `calc(100vh - ${topBarHeight}px)` },
              },
            }}
          >
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </Drawer>
        </Box>

        <Box
          component="main"
          sx={{
            flexGrow: 1,
            minWidth: 0,
            width: { xs: '100%', md: `calc(100% - ${drawerWidth}px)` },
          }}
        >
          <Box sx={{ p: { xs: 2, sm: 3, lg: 4 } }}>
            <Outlet />
          </Box>
        </Box>
      </Box>
    </Box>
  )
}
