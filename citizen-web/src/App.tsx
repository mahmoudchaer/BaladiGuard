import { Route, Routes } from 'react-router-dom';
import { AppShell } from '@/components/AppShell';
import { HomePage } from '@/pages/HomePage';
import { MapPage } from '@/pages/MapPage';
import { PublicDetailPage } from '@/pages/PublicDetailPage';
import { PublicReportsPage } from '@/pages/PublicReportsPage';
import { TrackPage } from '@/pages/TrackPage';
import { PrivacyPage } from '@/pages/PrivacyPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { LoginPage } from '@/pages/LoginPage';
import { ProfilePage } from '@/pages/ProfilePage';
import { ReportPage } from '@/pages/ReportPage';
import { HistoryPage } from '@/pages/HistoryPage';
import { ProtectedRoute } from '@/auth/ProtectedRoute';
import { CitizenAuthProvider } from '@/auth/CitizenAuthContext';
import { LocaleProvider } from '@/i18n/LocaleProvider';
import { NotificationLinkPage } from '@/pages/NotificationLinkPage';
import '@/components/AppShell.css';
import '@/a11y.css';

function RouteTree() {
  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<HomePage />} />
          <Route path="reports" element={<PublicReportsPage />} />
          <Route path="map" element={<MapPage />} />
          <Route path="public/:ticketNumber" element={<PublicDetailPage />} />
          <Route path="t/:code" element={<NotificationLinkPage />} />
          <Route path="track" element={<TrackPage />} />
          <Route path="privacy" element={<PrivacyPage />} />
          <Route path="login" element={<LoginPage />} />
          <Route path="report" element={<ReportPage />} />
          <Route
            path="history"
            element={
              <ProtectedRoute>
                <HistoryPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="profile"
            element={
              <ProtectedRoute>
                <ProfilePage />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </>
  );
}

export function AppRoutes() {
  return (
    <LocaleProvider>
      <CitizenAuthProvider>
        <RouteTree />
      </CitizenAuthProvider>
    </LocaleProvider>
  );
}

export function App() {
  return <AppRoutes />;
}
