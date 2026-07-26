import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { TicketListPage } from '@/pages/TicketListPage';
import { TicketDetailPage } from '@/pages/TicketDetailPage';
import { MapViewPage } from '@/pages/MapViewPage';
import '@/pages/TicketListPage.css';

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<TicketListPage />} />
        <Route path="/map" element={<MapViewPage />} />
        <Route path="/tickets/:ticketId" element={<TicketDetailPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
