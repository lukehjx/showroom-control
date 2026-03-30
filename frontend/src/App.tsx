import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './components/MainLayout'
import Dashboard from './pages/Dashboard'
import ReceptionPresets from './pages/ReceptionPresets'
import ExhibitScripts from './pages/ExhibitScripts'
import FlowEditor from './pages/FlowEditor'
import TourRoutes from './pages/TourRoutes'
import NavPositions from './pages/NavPositions'
import Appointments from './pages/Appointments'
import ScheduledTasks from './pages/ScheduledTasks'
import SyncManage from './pages/SyncManage'
import NotifyGroups from './pages/NotifyGroups'
import OperationLogs from './pages/OperationLogs'
import Settings from './pages/Settings'
import ChatLogs from './pages/ChatLogs'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="presets" element={<ReceptionPresets />} />
          <Route path="exhibits" element={<ExhibitScripts />} />
          <Route path="flows" element={<FlowEditor />} />
          <Route path="flows/:id" element={<FlowEditor />} />
          <Route path="tours" element={<TourRoutes />} />
          <Route path="positions" element={<NavPositions />} />
          <Route path="appointments" element={<Appointments />} />
          <Route path="tasks" element={<ScheduledTasks />} />
          <Route path="sync" element={<SyncManage />} />
          <Route path="notify" element={<NotifyGroups />} />
          <Route path="logs" element={<OperationLogs />} />
          <Route path="chat-logs" element={<ChatLogs />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
