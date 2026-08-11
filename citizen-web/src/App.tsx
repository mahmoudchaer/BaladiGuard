import { Route, Routes } from 'react-router-dom';
import { AppShell } from '@/components/AppShell';
import { HomePage } from '@/pages/HomePage';
import { MapPage } from '@/pages/MapPage';
import { PublicDetailPage } from '@/pages/PublicDetailPage';
import { TrackPage } from '@/pages/TrackPage';
import { PrivacyPage } from '@/pages/PrivacyPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { StubPage } from '@/pages/StubPage';
import '@/components/AppShell.css';

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="map" element={<MapPage />} />
        <Route path="public/:ticketNumber" element={<PublicDetailPage />} />
        <Route path="track" element={<TrackPage />} />
        <Route path="privacy" element={<PrivacyPage />} />
        <Route
          path="login"
          element={
            <StubPage
              title="Sign in"
              message="Citizen account sign-in arrives in the follow-up Sprint 7 issue. Guests can still browse public reports and track by code."
            />
          }
        />
        <Route
          path="report"
          element={
            <StubPage
              title="Submit a report"
              message="Web report creation is planned for the citizen account/contribution follow-up. Use the mobile app to submit today."
            />
          }
        />
        <Route
          path="history"
          element={
            <StubPage
              title="My history"
              message="Signed-in report history will ship with citizen accounts. Track an existing submission with your 6-character code."
            />
          }
        />
        <Route
          path="profile"
          element={
            <StubPage
              title="Profile"
              message="Citizen profile settings are part of the authenticated web follow-up."
            />
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export function App() {
  return <AppRoutes />;
}
