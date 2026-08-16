import {
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from 'react';
import { useNavigate } from 'react-router-dom';
import { queryStaffAssistant } from '@/services/staffAssistant';
import type { StaffAssistantAreaCluster, StaffAssistantResponse } from '@/types/staffAssistant';
import {
  assistantFiltersFromApplied,
  buildMapPath,
  buildTicketDetailPath,
  buildTicketListPath,
} from '@/utils/dashboardNavigation';
import type { TicketPriority, TicketStatus } from '@/types/ticket';
import { getLocale } from '@/i18n';
import { useI18n } from '@/i18n/LocaleProvider';
import { formatCategory, formatPriority, formatStatus } from '@/utils/labels';
import './StaffAssistantPanel.css';

const SUGGESTION_KEYS = [
  'assistant.suggestionHighPriority',
  'assistant.suggestionRepeated',
  'assistant.suggestionUrgentFr',
  'assistant.suggestionRepeatedAr',
] as const;

type StaffAssistantPanelProps = {
  open: boolean;
  onClose: () => void;
};

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'textarea:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

function focusableElements(container: HTMLElement): HTMLElement[] {
  return [...container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)].filter(
    (element) =>
      !element.hasAttribute('disabled') && element.getAttribute('aria-hidden') !== 'true',
  );
}

function formatAsOf(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(getLocale(), {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed);
}

function clusterMapFilters(cluster: StaffAssistantAreaCluster) {
  if (
    cluster.south == null ||
    cluster.west == null ||
    cluster.north == null ||
    cluster.east == null
  ) {
    return null;
  }
  return {
    openOnly: true,
    south: cluster.south,
    west: cluster.west,
    north: cluster.north,
    east: cluster.east,
    zoom: 16,
  };
}

export function StaffAssistantPanel({ open, onClose }: StaffAssistantPanelProps) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const titleId = useId();
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLElement>(null);
  const [question, setQuestion] = useState('');
  const [loadState, setLoadState] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [answer, setAnswer] = useState<StaffAssistantResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    inputRef.current?.focus();
    return () => {
      previous?.focus();
    };
  }, [open]);

  function trapTab(event: ReactKeyboardEvent<HTMLElement> | KeyboardEvent) {
    if (event.key !== 'Tab' || !panelRef.current) {
      return;
    }
    const focusable = focusableElements(panelRef.current);
    if (focusable.length === 0) {
      event.preventDefault();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && (active === first || !panelRef.current.contains(active))) {
      event.preventDefault();
      last.focus();
      return;
    }
    if (!event.shiftKey && (active === last || !panelRef.current.contains(active))) {
      event.preventDefault();
      first.focus();
    }
  }

  useEffect(() => {
    if (!open) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      trapTab(event);
    }
    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [open, onClose]);

  async function ask(nextQuestion: string) {
    const trimmed = nextQuestion.trim();
    if (!trimmed) {
      return;
    }
    setQuestion(trimmed);
    setLoadState('loading');
    setErrorMessage(null);
    try {
      const response = await queryStaffAssistant(trimmed);
      setAnswer(response);
      setLoadState('success');
    } catch (error) {
      setAnswer(null);
      setErrorMessage(error instanceof Error ? error.message : t('assistant.errorFallback'));
      setLoadState('error');
    }
  }

  if (!open) {
    return null;
  }

  const listFilters = answer ? assistantFiltersFromApplied(answer.appliedFilters) : {};
  const canViewTickets = Boolean(answer && answer.intent !== 'unsupported');

  return (
    <aside
      ref={panelRef}
      id="staff-assistant-panel"
      className="staff-assistant-panel"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onKeyDown={trapTab}
    >
      <header className="staff-assistant-panel__header">
        <div>
          <h2 id={titleId} className="staff-assistant-panel__title">
            {t('assistant.title')}
          </h2>
          <p className="staff-assistant-panel__subtitle">{t('assistant.subtitle')}</p>
        </div>
        <button type="button" className="staff-assistant-panel__close" onClick={onClose}>
          {t('common.close')}
        </button>
      </header>

      <div className="staff-assistant-panel__body">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void ask(question);
          }}
        >
          <label className="staff-assistant-panel__label" htmlFor={inputId}>
            {t('assistant.askLabel')}
          </label>
          <input
            ref={inputRef}
            id={inputId}
            className="staff-assistant-panel__input"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            maxLength={500}
            autoComplete="off"
          />
        </form>

        <div
          className="staff-assistant-panel__suggestions"
          role="group"
          aria-label={t('assistant.suggestions')}
        >
          {SUGGESTION_KEYS.map((key) => (
            <button
              key={key}
              type="button"
              className="staff-assistant-panel__suggestion"
              onClick={() => void ask(t(key))}
            >
              {t(key)}
            </button>
          ))}
        </div>

        {loadState === 'loading' && (
          <p className="staff-assistant-panel__status" role="status">
            {t('assistant.loading')}
          </p>
        )}

        {loadState === 'error' && (
          <div className="staff-assistant-panel__error" role="alert">
            <p>{errorMessage}</p>
            <button
              type="button"
              className="staff-assistant-panel__retry"
              onClick={() => void ask(question)}
            >
              {t('common.tryAgain')}
            </button>
          </div>
        )}

        {loadState === 'success' && answer && (
          <div className="staff-assistant-panel__answer">
            <p className="staff-assistant-panel__message">{answer.message}</p>
            <p className="staff-assistant-panel__meta">
              {t(answer.count === 1 ? 'assistant.matchingRecord' : 'assistant.matchingRecords', {
                count: answer.count,
                asOf: formatAsOf(answer.asOf),
              })}
            </p>
            {answer.incompleteCount > 0 ? (
              <p className="staff-assistant-panel__limit">
                {t('assistant.pendingClassification', { count: answer.incompleteCount })}
              </p>
            ) : null}
            {answer.unlocatedCount > 0 ? (
              <p className="staff-assistant-panel__limit">
                {t('assistant.omittedUnlocated', { count: answer.unlocatedCount })}
              </p>
            ) : null}
            {answer.areaClustersTruncated ? (
              <p className="staff-assistant-panel__limit">
                {t('assistant.topAreas', {
                  shown: answer.areaClusters.length,
                  total: answer.areaClusterTotal,
                })}
              </p>
            ) : null}
            {answer.count === 0 ? (
              <p className="staff-assistant-panel__empty">{t('assistant.empty')}</p>
            ) : null}

            {canViewTickets ? (
              <div className="staff-assistant-panel__actions">
                <button
                  type="button"
                  className="staff-assistant-panel__action"
                  onClick={() => {
                    navigate(buildTicketListPath(listFilters));
                    onClose();
                  }}
                >
                  {t('assistant.viewTickets')}
                </button>
                <button
                  type="button"
                  className="staff-assistant-panel__action staff-assistant-panel__action--secondary"
                  onClick={() => {
                    navigate(buildMapPath(listFilters));
                    onClose();
                  }}
                >
                  {t('assistant.viewMap')}
                </button>
              </div>
            ) : null}

            {answer.areaClusters.length > 0 ? (
              <ul className="staff-assistant-panel__clusters">
                {answer.areaClusters.map((cluster) => {
                  const mapFilters = clusterMapFilters(cluster);
                  return (
                    <li key={cluster.cellId} className="staff-assistant-panel__cluster">
                      <p className="staff-assistant-panel__cluster-title">{cluster.label}</p>
                      <p className="staff-assistant-panel__cluster-meta">
                        {t('assistant.clusterMeta', {
                          reports: cluster.distinctReportCount,
                          tickets: cluster.ticketCount,
                        })}
                        {cluster.ticketIdsTruncated ? t('assistant.clusterTruncated') : ''}
                      </p>
                      <div className="staff-assistant-panel__actions">
                        <button
                          type="button"
                          className="staff-assistant-panel__action"
                          onClick={() => {
                            navigate(
                              buildTicketListPath({
                                openOnly: true,
                                ticketIds: cluster.ticketIds,
                              }),
                            );
                            onClose();
                          }}
                        >
                          {t('assistant.viewTickets')}
                        </button>
                        {mapFilters ? (
                          <button
                            type="button"
                            className="staff-assistant-panel__action staff-assistant-panel__action--secondary"
                            onClick={() => {
                              navigate(buildMapPath(mapFilters));
                              onClose();
                            }}
                          >
                            {t('assistant.viewMap')}
                          </button>
                        ) : null}
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : null}

            {answer.tickets.length > 0 ? (
              <ul className="staff-assistant-panel__tickets">
                {answer.tickets.map((ticket) => (
                  <li key={ticket.ticketId} className="staff-assistant-panel__ticket">
                    <p className="staff-assistant-panel__ticket-id">{ticket.ticketNumber}</p>
                    <p className="staff-assistant-panel__ticket-meta">
                      {formatCategory(ticket.category)} ·{' '}
                      {formatStatus(ticket.status as TicketStatus)}
                      {ticket.priority
                        ? ` · ${formatPriority(ticket.priority as TicketPriority)}`
                        : ''}
                    </p>
                    <button
                      type="button"
                      className="staff-assistant-panel__action staff-assistant-panel__action--secondary"
                      onClick={() => {
                        navigate(buildTicketDetailPath(ticket.ticketId));
                        onClose();
                      }}
                    >
                      {t('assistant.openTicket')}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        )}
      </div>
    </aside>
  );
}
