import { useEffect, useState } from 'react';
import { useI18n } from '@/i18n/LocaleProvider';
import { fetchAssignmentHistory, type AssignmentHistoryItem } from '@/services/tickets';

function actionLabel(actionType: string, translate: (key: string) => string): string {
  if (actionType === 'DEPARTMENT_ASSIGN') return translate('ticket.assignmentHistory.department');
  if (actionType === 'WORKFORCE_ASSIGN') return translate('ticket.assignmentHistory.workforce');
  if (actionType === 'WORK_ORDER_ASSIGN') return translate('ticket.assignmentHistory.workOrder');
  return actionType;
}

export function TicketAssignmentHistory({ ticketId }: { ticketId: string }) {
  const { t } = useI18n();
  const [items, setItems] = useState<AssignmentHistoryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setItems(null);
    setError(null);
    void fetchAssignmentHistory(ticketId)
      .then((response) => {
        if (!cancelled) setItems(response.items);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t('ticket.assignmentHistory.unableLoad'));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [t, ticketId]);

  return (
    <div className="ticket-detail__action-group">
      <p className="ticket-detail__eyebrow">{t('ticket.assignmentHistory.title')}</p>
      {error ? (
        <p className="ticket-detail__status-error" role="alert">
          {error}
        </p>
      ) : null}
      {!error && items && items.length === 0 ? (
        <p className="ticket-detail__card-hint">{t('ticket.assignmentHistory.empty')}</p>
      ) : null}
      {items && items.length > 0 ? (
        <ol className="ticket-assignment-history">
          {items.map((item) => (
            <li key={item.eventId || `${item.actionType}-${item.occurredAt}`}>
              <strong>{actionLabel(item.actionType, t)}</strong>
              {item.summary ? ` — ${item.summary}` : ''}
              {item.occurredAt ? (
                <>
                  {' '}
                  <time dateTime={item.occurredAt}>{item.occurredAt}</time>
                </>
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}
