import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { Ticket, TicketStatus } from '@/types/ticket';
import {
  assignTicketDepartment,
  reviewTicketCategory,
  updateTicketPublicContent,
  updateTicketStatus,
} from '@/services/tickets';
import { StatusBadge } from '@/components/StatusBadge';
import { PriorityBadge } from '@/components/PriorityBadge';
import { CategoryBadge } from '@/components/CategoryBadge';
import { TicketPhoto } from '@/components/TicketPhoto';
import { ImagePrivacyStatus } from '@/components/ImagePrivacyStatus';
import { DEPARTMENT_OPTIONS, formatDepartment } from '@/utils/departments';
import {
  formatCategory,
  formatCreatedDate,
  formatStatus,
  formatTicketAge,
  SUPPORTED_CATEGORY_OPTIONS,
} from '@/utils/labels';
import { getStaffNextAction } from '@/utils/reportGuidance';
import { getSelectableTicketStatuses } from '@/utils/statusTransitions';
import { reasonsForKind, requiredOutcomeKind } from '@/utils/outcomeReasons';
import './TicketPreviewPanel.css';

type TicketPreviewPanelProps = {
  ticket: Ticket | null;
  onTicketUpdated?: (ticket: Ticket) => void;
};

export function TicketPreviewPanel({ ticket, onTicketUpdated }: TicketPreviewPanelProps) {
  const [pendingStatus, setPendingStatus] = useState<TicketStatus | ''>('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedDepartmentId, setSelectedDepartmentId] = useState('');
  const [publicDescription, setPublicDescription] = useState('');
  const [publicLocationLabel, setPublicLocationLabel] = useState('');
  const [isSavingCategory, setIsSavingCategory] = useState(false);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [isSavingDepartment, setIsSavingDepartment] = useState(false);
  const [isSavingPublic, setIsSavingPublic] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [statusReasonCode, setStatusReasonCode] = useState('');
  const [statusPrivateNote, setStatusPrivateNote] = useState('');

  useEffect(() => {
    if (!ticket) {
      return;
    }
    setPendingStatus(ticket.status);
    setSelectedCategory(ticket.ai?.finalCategory ?? ticket.ai?.aiSuggestedCategory ?? '');
    setSelectedDepartmentId(ticket.departmentId ?? '');
    setPublicDescription(ticket.public?.description ?? '');
    setPublicLocationLabel(ticket.public?.locationLabel ?? '');
    setActionError(null);
    setActionSuccess(null);
    setStatusReasonCode('');
    setStatusPrivateNote('');
  }, [ticket]);

  if (!ticket) {
    return (
      <aside className="ticket-preview" aria-label="Ticket preview">
        <div className="ticket-preview__empty">
          <p className="ticket-preview__empty-title">Select a report</p>
          <p className="ticket-preview__empty-body">
            Choose a ticket from the queue to review AI classification, update status, and assign a
            department — or open the full ticket for history and duplicates.
          </p>
        </div>
      </aside>
    );
  }

  const department = ticket.departmentName ?? formatDepartment(ticket.departmentId);

  async function handleAcceptAi() {
    const suggestion = ticket?.ai?.aiSuggestedCategory;
    if (!ticket || !suggestion) {
      return;
    }
    setIsSavingCategory(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await reviewTicketCategory(ticket.ticketId, { finalCategory: suggestion });
      if (!updated) {
        setActionError('Unable to save AI category.');
        return;
      }
      onTicketUpdated?.(updated);
      setActionSuccess('AI category accepted.');
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Unable to accept AI suggestion.');
    } finally {
      setIsSavingCategory(false);
    }
  }

  async function handleSaveCategory() {
    if (!ticket || !selectedCategory) {
      return;
    }
    setIsSavingCategory(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await reviewTicketCategory(ticket.ticketId, {
        finalCategory: selectedCategory,
      });
      if (!updated) {
        setActionError('Unable to save category.');
        return;
      }
      onTicketUpdated?.(updated);
      setActionSuccess('Final category saved.');
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Unable to save category.');
    } finally {
      setIsSavingCategory(false);
    }
  }

  async function handleApplyStatus() {
    if (!ticket || !pendingStatus || pendingStatus === ticket.status) {
      return;
    }
    const outcomeKind = requiredOutcomeKind(ticket.status, pendingStatus);
    if (outcomeKind && !statusReasonCode) {
      setActionError('Select a structured reason before applying this status.');
      return;
    }
    setIsUpdatingStatus(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await updateTicketStatus(ticket.ticketId, pendingStatus, {
        reasonCode: outcomeKind ? statusReasonCode : undefined,
        note: statusPrivateNote.trim() || undefined,
      });
      if (!updated) {
        setActionError('Unable to update status.');
        return;
      }
      onTicketUpdated?.(updated);
      setActionSuccess('Status updated.');
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Unable to update status.');
    } finally {
      setIsUpdatingStatus(false);
    }
  }

  async function handleSaveDepartment() {
    if (!ticket || !selectedDepartmentId) {
      return;
    }
    setIsSavingDepartment(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await assignTicketDepartment(ticket.ticketId, {
        departmentId: selectedDepartmentId,
      });
      if (!updated) {
        setActionError('Unable to save department.');
        return;
      }
      onTicketUpdated?.(updated);
      setActionSuccess('Department assigned.');
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Unable to save department.');
    } finally {
      setIsSavingDepartment(false);
    }
  }

  async function handleSavePublicContent(publicStatus: 'PUBLISHED' | 'UNPUBLISHED') {
    if (!ticket) {
      return;
    }
    setIsSavingPublic(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await updateTicketPublicContent(ticket.ticketId, {
        publicStatus,
        publicDescription,
        publicLocationLabel,
        clearPublicPhoto: undefined,
      });
      if (!updated) {
        setActionError('Unable to update public content.');
        return;
      }
      onTicketUpdated?.(updated);
      setActionSuccess(
        publicStatus === 'PUBLISHED'
          ? 'Published to the public feed.'
          : 'Removed from the public feed.',
      );
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Unable to update public content.');
    } finally {
      setIsSavingPublic(false);
    }
  }

  return (
    <aside className="ticket-preview" aria-label="Ticket preview">
      <header className="ticket-preview__header">
        <div>
          <p className="ticket-preview__eyebrow">{ticket.trackingCode}</p>
          <h2 className="ticket-preview__title">{ticket.ticketNumber}</h2>
          <p className="ticket-preview__sub">
            Reported {formatCreatedDate(ticket.createdAt)} · {formatTicketAge(ticket.createdAt)} old
          </p>
        </div>
        <div className="ticket-preview__badges">
          <StatusBadge status={ticket.status} />
          <PriorityBadge priority={ticket.priority} />
        </div>
      </header>

      <div className="ticket-preview__body">
        <section className="ticket-preview__section">
          <h3 className="ticket-preview__section-title">Next action</h3>
          <p className="ticket-preview__next">{getStaffNextAction(ticket.status)}</p>
        </section>

        <section
          className="ticket-preview__section ticket-preview__section--ai"
          aria-labelledby="preview-ai-heading"
        >
          <h3 id="preview-ai-heading" className="ticket-preview__section-title">
            AI classification
          </h3>
          <p className="ticket-preview__ai-note">
            AI-generated — verify before accepting. Same controls as the full ticket.
          </p>

          {ticket.ai?.aiSuggestedCategory ? (
            <div className="ticket-preview__suggestion">
              <span className="ticket-preview__suggestion-label">Suggestion</span>
              <CategoryBadge category={ticket.ai.aiSuggestedCategory} />
              {ticket.ai.aiCategoryExplanation ? (
                <p className="ticket-preview__suggestion-text">{ticket.ai.aiCategoryExplanation}</p>
              ) : null}
            </div>
          ) : (
            <p className="ticket-preview__muted">No AI category suggestion yet.</p>
          )}

          {ticket.ai?.finalCategory ? (
            <div className="ticket-preview__final">
              <span>Final</span>
              <CategoryBadge category={ticket.ai.finalCategory} />
            </div>
          ) : null}

          <label className="ticket-preview__field">
            <span>Final category</span>
            <select
              value={selectedCategory}
              onChange={(event) => setSelectedCategory(event.target.value)}
              disabled={isSavingCategory || ticket.ai?.aiProcessingStatus === 'pending'}
            >
              <option value="">Select a category</option>
              {SUPPORTED_CATEGORY_OPTIONS.map((category) => (
                <option key={category} value={category}>
                  {formatCategory(category)}
                </option>
              ))}
            </select>
          </label>

          <div className="ticket-preview__actions">
            {ticket.ai?.aiSuggestedCategory ? (
              <button
                type="button"
                className="ticket-preview__btn ticket-preview__btn--secondary"
                onClick={() => void handleAcceptAi()}
                disabled={
                  isSavingCategory ||
                  ticket.ai.aiProcessingStatus === 'pending' ||
                  ticket.ai.finalCategory === ticket.ai.aiSuggestedCategory
                }
              >
                Accept AI suggestion
              </button>
            ) : null}
            <button
              type="button"
              className="ticket-preview__btn"
              onClick={() => void handleSaveCategory()}
              disabled={
                isSavingCategory || ticket.ai?.aiProcessingStatus === 'pending' || !selectedCategory
              }
            >
              {isSavingCategory ? 'Saving…' : 'Save final category'}
            </button>
          </div>
        </section>

        <section className="ticket-preview__section">
          <h3 className="ticket-preview__section-title">Municipal actions</h3>

          <label className="ticket-preview__field">
            <span>Status</span>
            <select
              value={pendingStatus || ticket.status}
              onChange={(event) => setPendingStatus(event.target.value as TicketStatus)}
              disabled={isUpdatingStatus}
            >
              {getSelectableTicketStatuses(ticket.status).map((status) => (
                <option key={status} value={status}>
                  {formatStatus(status)}
                </option>
              ))}
            </select>
          </label>
          {pendingStatus &&
            pendingStatus !== ticket.status &&
            requiredOutcomeKind(ticket.status, pendingStatus) && (
              <label className="ticket-preview__field">
                <span>Required reason</span>
                <select
                  value={statusReasonCode}
                  onChange={(event) => setStatusReasonCode(event.target.value)}
                  disabled={isUpdatingStatus}
                >
                  <option value="">Select a reason</option>
                  {reasonsForKind(requiredOutcomeKind(ticket.status, pendingStatus)!).map(
                    (reason) => (
                      <option key={reason.code} value={reason.code}>
                        {reason.label}
                      </option>
                    ),
                  )}
                </select>
              </label>
            )}
          <button
            type="button"
            className="ticket-preview__btn"
            onClick={() => void handleApplyStatus()}
            disabled={isUpdatingStatus || !pendingStatus || pendingStatus === ticket.status}
          >
            {isUpdatingStatus ? 'Applying…' : 'Apply status change'}
          </button>

          <label className="ticket-preview__field">
            <span>Department ({department})</span>
            <select
              value={selectedDepartmentId}
              onChange={(event) => setSelectedDepartmentId(event.target.value)}
              disabled={isSavingDepartment}
            >
              <option value="">Select a department</option>
              {DEPARTMENT_OPTIONS.map((option) => (
                <option key={option.departmentId} value={option.departmentId}>
                  {option.name}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="ticket-preview__btn"
            onClick={() => void handleSaveDepartment()}
            disabled={
              isSavingDepartment ||
              !selectedDepartmentId ||
              selectedDepartmentId === (ticket.departmentId ?? '')
            }
          >
            {isSavingDepartment ? 'Saving…' : 'Save department'}
          </button>
        </section>

        <section className="ticket-preview__section">
          <h3 className="ticket-preview__section-title">Evidence</h3>
          <TicketPhoto
            imageObjectKey={ticket.imageObjectKey}
            imageUrl={ticket.imageUrl}
            category={ticket.category}
            alt={`Report photo for ${ticket.ticketNumber}`}
          />
          <p className="ticket-preview__description">{ticket.description}</p>
          <p className="ticket-preview__location">{ticket.location.addressText}</p>
        </section>

        <section className="ticket-preview__section">
          <h3 className="ticket-preview__section-title">Public feed</h3>
          <p className="ticket-preview__hint">
            Approve a coarse public summary before publishing. Photos stay private until explicitly
            approved.
          </p>
          <label className="ticket-preview__field">
            <span>Public description</span>
            <textarea
              value={publicDescription}
              onChange={(event) => setPublicDescription(event.target.value)}
              rows={3}
              disabled={isSavingPublic}
            />
          </label>
          <label className="ticket-preview__field">
            <span>Public location label</span>
            <input
              type="text"
              value={publicLocationLabel}
              onChange={(event) => setPublicLocationLabel(event.target.value)}
              placeholder="e.g. Hamra, Beirut"
              disabled={isSavingPublic}
            />
          </label>
          <ImagePrivacyStatus redaction={ticket.imageRedaction} />
          <p className="ticket-preview__meta">
            Status: {ticket.public?.status ?? 'DRAFT'}
            {ticket.public?.imageObjectKey ? ' · photo approved' : ' · no public photo'}
          </p>
          <div className="ticket-preview__row">
            <button
              type="button"
              className="ticket-preview__btn ticket-preview__btn--primary"
              onClick={() => void handleSavePublicContent('PUBLISHED')}
              disabled={isSavingPublic || !publicDescription.trim() || !publicLocationLabel.trim()}
            >
              {isSavingPublic ? 'Saving…' : 'Publish'}
            </button>
            <button
              type="button"
              className="ticket-preview__btn"
              onClick={() => void handleSavePublicContent('UNPUBLISHED')}
              disabled={isSavingPublic || (ticket.public?.status ?? 'DRAFT') === 'DRAFT'}
            >
              Unpublish
            </button>
          </div>
        </section>

        {actionError ? (
          <p className="ticket-preview__error" role="alert">
            {actionError}
          </p>
        ) : null}
        {actionSuccess ? (
          <p className="ticket-preview__success" role="status">
            {actionSuccess}
          </p>
        ) : null}
      </div>

      <footer className="ticket-preview__footer">
        <Link to={`/tickets/${ticket.ticketId}`} className="ticket-preview__open">
          Open full ticket
        </Link>
      </footer>
    </aside>
  );
}
