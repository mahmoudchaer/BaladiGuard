import { useEffect, useId, useRef, useState } from 'react';
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
import { formatCategory, formatPriority, formatStatus } from '@/utils/labels';
import './StaffAssistantPanel.css';

const SUGGESTIONS = [
  'Show high-priority tickets',
  'Where are repeated problems?',
  'Quels tickets urgents?',
  'وين المشاكل المتكررة؟',
];

type StaffAssistantPanelProps = {
  open: boolean;
  onClose: () => void;
};

function formatAsOf(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
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
  const navigate = useNavigate();
  const titleId = useId();
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [question, setQuestion] = useState('');
  const [loadState, setLoadState] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [answer, setAnswer] = useState<StaffAssistantResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
    }
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
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
      setErrorMessage(
        error instanceof Error ? error.message : 'Unable to ask the staff assistant.',
      );
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
      id="staff-assistant-panel"
      className="staff-assistant-panel"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <header className="staff-assistant-panel__header">
        <div>
          <h2 id={titleId} className="staff-assistant-panel__title">
            Staff assistant
          </h2>
          <p className="staff-assistant-panel__subtitle">
            Ask about urgent tickets or repeated problem areas. Answers stay grounded in your
            visible records.
          </p>
        </div>
        <button type="button" className="staff-assistant-panel__close" onClick={onClose}>
          Close
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
            Ask a supported question
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
          aria-label="Suggested questions"
        >
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              className="staff-assistant-panel__suggestion"
              onClick={() => void ask(suggestion)}
            >
              {suggestion}
            </button>
          ))}
        </div>

        {loadState === 'loading' && (
          <p className="staff-assistant-panel__status" role="status">
            Checking current operational records…
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
              Try again
            </button>
          </div>
        )}

        {loadState === 'success' && answer && (
          <div className="staff-assistant-panel__answer">
            <p className="staff-assistant-panel__message">{answer.message}</p>
            <p className="staff-assistant-panel__meta">
              {answer.count} matching record{answer.count === 1 ? '' : 's'} · as of{' '}
              {formatAsOf(answer.asOf)}
            </p>
            {answer.incompleteCount > 0 ? (
              <p className="staff-assistant-panel__limit">
                {answer.incompleteCount} still pending classification.
              </p>
            ) : null}
            {answer.unlocatedCount > 0 ? (
              <p className="staff-assistant-panel__limit">
                {answer.unlocatedCount} omitted because coordinates are unusable.
              </p>
            ) : null}
            {answer.areaClustersTruncated ? (
              <p className="staff-assistant-panel__limit">
                Showing the top {answer.areaClusters.length} of {answer.areaClusterTotal} areas.
              </p>
            ) : null}
            {answer.count === 0 ? (
              <p className="staff-assistant-panel__empty">No matching operational records.</p>
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
                  View matching tickets
                </button>
                <button
                  type="button"
                  className="staff-assistant-panel__action staff-assistant-panel__action--secondary"
                  onClick={() => {
                    navigate(buildMapPath(listFilters));
                    onClose();
                  }}
                >
                  View on map
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
                        {cluster.distinctReportCount} distinct reports · {cluster.ticketCount}{' '}
                        tickets
                        {cluster.ticketIdsTruncated ? ' · sample truncated' : ''}
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
                          View matching tickets
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
                            View on map
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
                      Open ticket
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
