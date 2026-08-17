import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from '@/auth/ProtectedRoute';
import { StaffAuthProvider } from '@/auth/StaffAuthContext';
import { LocaleProvider } from '@/i18n/LocaleProvider';
import { TicketListPage } from '@/pages/TicketListPage';
import { TicketDetailPage } from '@/pages/TicketDetailPage';
import { MapViewPage } from '@/pages/MapViewPage';
import { WorkforcePage } from '@/pages/WorkforcePage';
import { LoginPage } from '@/pages/LoginPage';
import { ForgotPasswordPage } from '@/pages/ForgotPasswordPage';
import { ResetPasswordPage } from '@/pages/ResetPasswordPage';
import { StaffAccountsPage } from '@/pages/StaffAccountsPage';
import '@/pages/TicketListPage.css';

export function App() {
  return (
    <LocaleProvider>
      <StaffAuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <TicketListPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/map"
              element={
                <ProtectedRoute>
                  <MapViewPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/workforce"
              element={
                <ProtectedRoute>
                  <WorkforcePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/staff-accounts"
              element={
                <ProtectedRoute role="administrator">
                  <StaffAccountsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/tickets/:ticketId"
              element={
                <ProtectedRoute>
                  <TicketDetailPage />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </StaffAuthProvider>
    </LocaleProvider>
  );
}
