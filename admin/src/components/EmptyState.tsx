import './EmptyState.css';
import { IconDocument } from '@/components/icons';

type EmptyStateProps = {
  title?: string;
  message?: string;
};

export function EmptyState({
  title = 'No tickets yet',
  message = 'Submitted citizen reports will appear here once they are available.',
}: EmptyStateProps) {
  return (
    <div className="empty-state" role="status">
      <div className="empty-state__icon-wrap" aria-hidden="true">
        <IconDocument />
      </div>
      <h2 className="empty-state__title">{title}</h2>
      <p className="empty-state__message">{message}</p>
    </div>
  );
}
