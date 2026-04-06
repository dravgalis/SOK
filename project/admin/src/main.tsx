import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AdminLayout } from './layout/AdminLayout';
import { Candidates } from './pages/Candidates';
import { Dashboard } from './pages/Dashboard';
import { LoginPage } from './pages/LoginPage';
import { Settings } from './pages/Settings';
import { Vacancies } from './pages/Vacancies';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route path="/admin/login" element={<LoginPage />} />

        <Route
          path="/admin"
          element={
            <ProtectedRoute>
              <AdminLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="vacancies" element={<Vacancies />} />
          <Route path="candidates" element={<Candidates />} />
          <Route path="settings" element={<Settings />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
