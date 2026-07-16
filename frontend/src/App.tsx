import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'
import Register from './pages/Register'
import Chat from './pages/Chat'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/chat" element={<Chat />} />
            <Route path="/chat/:id" element={<Chat />} />
          </Route>
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
