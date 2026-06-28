import { Navigate, Route, Routes } from 'react-router-dom'

import AppLayout from '../layouts/AppLayout'
import ApprovalsPage from '../pages/ApprovalsPage'
import BudgetsPage from '../pages/BudgetsPage'
import ChatPage from '../pages/ChatPage'
import DashboardPage from '../pages/DashboardPage'
import LogsPage from '../pages/LogsPage'
import RulesPage from '../pages/RulesPage'

import { defaultRoutePath } from './navigation'

export default function AppRoutes() {
	return (
		<Routes>
			<Route element={<AppLayout />}>
				<Route path="/" element={<Navigate to={defaultRoutePath} replace />} />
				<Route path="/dashboard" element={<DashboardPage />} />
				<Route path="/chat" element={<ChatPage />} />
				<Route path="/rules" element={<RulesPage />} />
				<Route path="/approvals" element={<ApprovalsPage />} />
				<Route path="/budgets" element={<BudgetsPage />} />
				<Route path="/logs" element={<LogsPage />} />
			</Route>
		</Routes>
	)
}
