import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { searchStaffRecords } from '@/services/staffSearch';
import type { StaffSearchResponse } from '@/types/staffSearch';
import { buildTicketDetailPath, buildWorkforcePath } from '@/utils/dashboardNavigation';
import type { TicketStatus } from '@/types/ticket';
import { formatCategory, formatStatus } from '@/utils/labels';
import { IconSearch } from '@/components/icons';
import './GlobalSearch.css';

const SEARCH_DEBOUNCE_MS = import.meta.env.MODE === 'test' ? 0 : 300;

type SearchOption = {
  id: string;
  group: string;
  title: string;
  meta: string;
  href: string;
};

function buildOptions(results: StaffSearchResponse): SearchOption[] {
  return [
    ...results.tickets.map((item) => ({
      id: `ticket:${item.ticketId}`,
      group: 'Tickets',
      title: item.ticketNumber,
      meta: [
        item.trackingCode,
        formatCategory(item.category),
        formatStatus(item.status as TicketStatus),
        item.publicLocationLabel,
      ]
        .filter(Boolean)
        .join(' · '),
      href: buildTicketDetailPath(item.ticketId),
    })),
    ...results.workers.map((item) => ({
      id: `worker:${item.workerId}`,
      group: 'Workers',
      title: item.displayName,
      meta: item.active ? 'Active worker' : 'Inactive worker',
      href: buildWorkforcePath({ workerId: item.workerId }),
    })),
    ...results.teams.map((item) => ({
      id: `team:${item.teamId}`,
      group: 'Teams',
      title: item.displayName,
      meta: item.active ? 'Active team' : 'Inactive team',
      href: buildWorkforcePath({ teamId: item.teamId }),
    })),
    ...results.workOrders.map((item) => ({
      id: `work-order:${item.workOrderId}`,
      group: 'Work orders',
      title: item.ticketNumber ?? item.workOrderId,
      meta: `${item.state} · ${item.summary}`,
      href: buildTicketDetailPath(item.ticketId),
    })),
  ];
}

export function GlobalSearch() {
  const navigate = useNavigate();
  const inputId = useId();
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [loadState, setLoadState] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [results, setResults] = useState<StaffSearchResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const debouncedQuery = useDebouncedValue(query, SEARCH_DEBOUNCE_MS);

  useEffect(() => {
    const trimmed = debouncedQuery.trim();
    if (trimmed.length < 2) {
      setResults(null);
      setLoadState('idle');
      setErrorMessage(null);
      return;
    }
    const controller = new AbortController();
    setLoadState('loading');
    setErrorMessage(null);
    void searchStaffRecords(trimmed, controller.signal)
      .then((payload) => {
        if (controller.signal.aborted) {
          return;
        }
        setResults(payload);
        setLoadState('success');
        setActiveIndex(0);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        if (error instanceof DOMException && error.name === 'AbortError') {
          return;
        }
        setResults(null);
        setErrorMessage(error instanceof Error ? error.message : 'Unable to search.');
        setLoadState('error');
      });
    return () => controller.abort();
  }, [debouncedQuery]);

  const options = useMemo(() => (results ? buildOptions(results) : []), [results]);
  const groups = useMemo(() => {
    const next = new Map<string, SearchOption[]>();
    for (const option of options) {
      const current = next.get(option.group) ?? [];
      current.push(option);
      next.set(option.group, current);
    }
    return next;
  }, [options]);

  function closeSearch() {
    setOpen(false);
    setQuery('');
  }

  function choose(option: SearchOption) {
    navigate(option.href);
    closeSearch();
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      setOpen(false);
      return;
    }
    if (!open || options.length === 0) {
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveIndex((current) => (current + 1) % options.length);
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex((current) => (current - 1 + options.length) % options.length);
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      const selected = options[activeIndex];
      if (selected) {
        choose(selected);
      }
    }
  }

  const showPanel = open && query.trim().length >= 2;

  return (
    <div className="global-search">
      <label className="sr-only" htmlFor={inputId}>
        Search tickets, workers, teams, and work orders
      </label>
      <span className="global-search__icon" aria-hidden="true">
        <IconSearch />
      </span>
      <input
        ref={inputRef}
        id={inputId}
        className="global-search__input"
        type="search"
        role="combobox"
        aria-expanded={showPanel}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={
          showPanel && options[activeIndex] ? options[activeIndex].id : undefined
        }
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => {
          window.setTimeout(() => setOpen(false), 120);
        }}
        onKeyDown={onKeyDown}
        placeholder="Search ticket #, tracking, workers, teams…"
        autoComplete="off"
        maxLength={80}
      />
      {showPanel ? (
        <div className="global-search__panel" id={listId} role="listbox">
          {loadState === 'loading' ? (
            <p className="global-search__status" role="status">
              Searching permitted records…
            </p>
          ) : null}
          {loadState === 'error' ? (
            <p className="global-search__error" role="alert">
              {errorMessage}
            </p>
          ) : null}
          {loadState === 'success' && options.length === 0 ? (
            <p className="global-search__empty">No matching operational records.</p>
          ) : null}
          {loadState === 'success'
            ? [...groups.entries()].map(([group, items]) => (
                <div key={group} className="global-search__group">
                  <p className="global-search__group-title">{group}</p>
                  {items.map((option) => {
                    const index = options.findIndex((item) => item.id === option.id);
                    return (
                      <button
                        key={option.id}
                        id={option.id}
                        type="button"
                        role="option"
                        aria-selected={index === activeIndex}
                        className="global-search__option"
                        onMouseDown={(event) => event.preventDefault()}
                        onClick={() => {
                          navigate(option.href);
                          closeSearch();
                        }}
                      >
                        <span className="global-search__option-title">{option.title}</span>
                        <span className="global-search__option-meta">{option.meta}</span>
                      </button>
                    );
                  })}
                </div>
              ))
            : null}
          {results?.partialFailures.length ? (
            <p className="global-search__note" role="status">
              Some search groups could not be loaded: {results.partialFailures.join(', ')}.
            </p>
          ) : null}
          {results?.scanTruncated ? (
            <p className="global-search__note">
              Ticket text search is limited to the newest permitted records. Use a ticket or
              tracking number for an exact lookup.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
