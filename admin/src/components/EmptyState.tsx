import './EmptyState.css';
import { CivicIllustration, type AdminIllustrationName } from '@/components/CivicIllustration';

type EmptyStateProps = {
  title?: string;
  message?: string;
  visual?: AdminIllustrationName;
};

export function EmptyState({
  title = 'No tickets yet',
  message = 'Submitted citizen reports will appear here once they are available.',
  visual = 'tickets',
}: EmptyStateProps) {
  return (
    <div className="empty-state" role="status">
      <CivicIllustration name={visual} />
      <h2 className="empty-state__title">{title}</h2>
      <p className="empty-state__message">{message}</p>
    </div>
  );
}
