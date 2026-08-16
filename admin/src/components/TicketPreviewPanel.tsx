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
import { useI18n } from '@/i18n/LocaleProvider';
import './TicketPreviewPanel.css';

type TicketPreviewPanelProps = {
  ticket: Ticket | null;
  onTicketUpdated?: (ticket: Ticket) => void;
};

type ActionNotice = { tone: 'error' | 'success'; key: string } | { tone: 'error'; text: string };

export function TicketPreviewPanel({ ticket, onTicketUpdated }: TicketPreviewPanelProps) {
  const { t } = useI18n();
  const [pendingStatus, setPendingStatus] = useState<TicketStatus | ''>('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedDepartmentId, setSelectedDepartmentId] = useState('');
  const [publicDescription, setPublicDescription] = useState('');
  const [publicLocationLabel, setPublicLocationLabel] = useState('');
  const [isSavingCategory, setIsSavingCategory] = useState(false);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [isSavingDepartment, setIsSavingDepartment] = useState(false);
  const [isSavingPublic, setIsSavingPublic] = useState(false);
  const [actionNotice, setActionNotice] = useState<ActionNotice | null>(null);
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
    setActionNotice(null);
    setStatusReasonCode('');
    setStatusPrivateNote('');
  }, [ticket]);

  if (!ticket) {
    return (
      <aside className="ticket-preview" aria-label={t('ticket.preview.a11y')}>
        <div className="ticket-preview__empty">
          <p className="ticket-preview__empty-title">{t('ticket.preview.selectReport')}</p>
          <p className="ticket-preview__empty-body">{t('ticket.preview.selectReportHint')}</p>
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
    setActionNotice(null);
    try {
      const updated = await reviewTicketCategory(ticket.ticketId, { finalCategory: suggestion });
      if (!updated) {
        setActionNotice({ tone: 'error', key: 'ticket.preview.unableSaveAi' });
        return;
      }
      onTicketUpdated?.(updated);
      setActionNotice({ tone: 'success', key: 'ticket.preview.aiAccepted' });
    } catch (error) {
      setActionNotice(
        error instanceof Error
          ? { tone: 'error', text: error.message }
          : { tone: 'error', key: 'ticket.preview.unableAcceptAi' },
      );
    } finally {
      setIsSavingCategory(false);
    }
  }

  async function handleSaveCategory() {
    if (!ticket || !selectedCategory) {
      return;
    }
    setIsSavingCategory(true);
    setActionNotice(null);
    try {
      const updated = await reviewTicketCategory(ticket.ticketId, {
        finalCategory: selectedCategory,
      });
      if (!updated) {
        setActionNotice({ tone: 'error', key: 'ticket.preview.unableSaveCategory' });
        return;
      }
      onTicketUpdated?.(updated);
      setActionNotice({ tone: 'success', key: 'ticket.preview.categorySaved' });
    } catch (error) {
      setActionNotice(
        error instanceof Error
          ? { tone: 'error', text: error.message }
          : { tone: 'error', key: 'ticket.preview.unableSaveCategory' },
      );
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
      setActionNotice({ tone: 'error', key: 'ticket.review.selectReasonBeforeStatus' });
      return;
    }
    setIsUpdatingStatus(true);
    setActionNotice(null);
    try {
      const updated = await updateTicketStatus(ticket.ticketId, pendingStatus, {
        reasonCode: outcomeKind ? statusReasonCode : undefined,
        note: statusPrivateNote.trim() || undefined,
      });
      if (!updated) {
        setActionNotice({ tone: 'error', key: 'ticket.preview.unableUpdateStatus' });
        return;
      }
      onTicketUpdated?.(updated);
      setActionNotice({ tone: 'success', key: 'ticket.preview.statusUpdated' });
    } catch (error) {
      setActionNotice(
        error instanceof Error
          ? { tone: 'error', text: error.message }
          : { tone: 'error', key: 'ticket.preview.unableUpdateStatus' },
      );
    } finally {
      setIsUpdatingStatus(false);
    }
  }

  async function handleSaveDepartment() {
    if (!ticket || !selectedDepartmentId) {
      return;
    }
    setIsSavingDepartment(true);
    setActionNotice(null);
    try {
      const updated = await assignTicketDepartment(ticket.ticketId, {
        departmentId: selectedDepartmentId,
      });
      if (!updated) {
        setActionNotice({ tone: 'error', key: 'ticket.preview.unableSaveDepartment' });
        return;
      }
      onTicketUpdated?.(updated);
      setActionNotice({ tone: 'success', key: 'ticket.preview.departmentAssigned' });
    } catch (error) {
      setActionNotice(
        error instanceof Error
          ? { tone: 'error', text: error.message }
          : { tone: 'error', key: 'ticket.preview.unableSaveDepartment' },
      );
    } finally {
      setIsSavingDepartment(false);
    }
  }

  async function handleSavePublicContent(publicStatus: 'PUBLISHED' | 'UNPUBLISHED') {
    if (!ticket) {
      return;
    }
    setIsSavingPublic(true);
    setActionNotice(null);
    try {
      const updated = await updateTicketPublicContent(ticket.ticketId, {
        publicStatus,
        publicDescription,
        publicLocationLabel,
        clearPublicPhoto: undefined,
      });
      if (!updated) {
        setActionNotice({ tone: 'error', key: 'ticket.preview.unableUpdatePublic' });
        return;
      }
      onTicketUpdated?.(updated);
      setActionNotice({
        tone: 'success',
        key:
          publicStatus === 'PUBLISHED' ? 'ticket.preview.published' : 'ticket.preview.unpublished',
      });
    } catch (error) {
      setActionNotice(
        error instanceof Error
          ? { tone: 'error', text: error.message }
          : { tone: 'error', key: 'ticket.preview.unableUpdatePublic' },
      );
    } finally {
      setIsSavingPublic(false);
    }
  }

  return (
    <aside className="ticket-preview" aria-label={t('ticket.preview.a11y')}>
      <header className="ticket-preview__header">
        <div>
          <p className="ticket-preview__eyebrow">{ticket.trackingCode}</p>
          <h2 className="ticket-preview__title">{ticket.ticketNumber}</h2>
          <p className="ticket-preview__sub">
            {t('ticket.preview.reportedAge', {
              date: formatCreatedDate(ticket.createdAt),
              age: formatTicketAge(ticket.createdAt),
            })}
          </p>
        </div>
        <div className="ticket-preview__badges">
          <StatusBadge status={ticket.status} />
          <PriorityBadge priority={ticket.priority} />
        </div>
      </header>

      <div className="ticket-preview__body">
        <section className="ticket-preview__section">
          <h3 className="ticket-preview__section-title">{t('ticket.nextAction')}</h3>
          <p className="ticket-preview__next">{getStaffNextAction(ticket.status)}</p>
        </section>

        <section
          className="ticket-preview__section ticket-preview__section--ai"
          aria-labelledby="preview-ai-heading"
        >
          <h3 id="preview-ai-heading" className="ticket-preview__section-title">
            {t('ticket.preview.aiClassification')}
          </h3>
          <p className="ticket-preview__ai-note">{t('ticket.preview.aiHint')}</p>

          {ticket.ai?.aiSuggestedCategory ? (
            <div className="ticket-preview__suggestion">
              <span className="ticket-preview__suggestion-label">
                {t('ticket.preview.suggestion')}
              </span>
              <CategoryBadge category={ticket.ai.aiSuggestedCategory} />
              {ticket.ai.aiCategoryExplanation ? (
                <p className="ticket-preview__suggestion-text">{ticket.ai.aiCategoryExplanation}</p>
              ) : null}
            </div>
          ) : (
            <p className="ticket-preview__muted">{t('ticket.preview.noAiSuggestion')}</p>
          )}

          {ticket.ai?.finalCategory ? (
            <div className="ticket-preview__final">
              <span>{t('ticket.preview.final')}</span>
              <CategoryBadge category={ticket.ai.finalCategory} />
            </div>
          ) : null}

          <label className="ticket-preview__field">
            <span>{t('ticket.review.finalCategory')}</span>
            <select
              value={selectedCategory}
              onChange={(event) => setSelectedCategory(event.target.value)}
              disabled={isSavingCategory || ticket.ai?.aiProcessingStatus === 'pending'}
            >
              <option value="">{t('ticket.review.selectCategory')}</option>
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
                {t('ticket.review.acceptAi')}
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
              {isSavingCategory ? t('ticket.preview.saving') : t('ticket.review.saveFinalCategory')}
            </button>
          </div>
        </section>

        <section className="ticket-preview__section">
          <h3 className="ticket-preview__section-title">{t('ticket.review.municipalTitle')}</h3>

          <label className="ticket-preview__field">
            <span>{t('ticket.status')}</span>
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
                <span>{t('ticket.review.requiredReason')}</span>
                <select
                  value={statusReasonCode}
                  onChange={(event) => setStatusReasonCode(event.target.value)}
                  disabled={isUpdatingStatus}
                >
                  <option value="">{t('ticket.review.selectReason')}</option>
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
            {isUpdatingStatus ? t('ticket.preview.applying') : t('ticket.review.applyStatus')}
          </button>

          <label className="ticket-preview__field">
            <span>{t('ticket.preview.departmentValue', { department })}</span>
            <select
              value={selectedDepartmentId}
              onChange={(event) => setSelectedDepartmentId(event.target.value)}
              disabled={isSavingDepartment}
            >
              <option value="">{t('ticket.review.selectDepartment')}</option>
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
            {isSavingDepartment ? t('ticket.preview.saving') : t('ticket.review.saveDepartment')}
          </button>
        </section>

        <section className="ticket-preview__section">
          <h3 className="ticket-preview__section-title">{t('ticket.preview.evidence')}</h3>
          <TicketPhoto
            imageObjectKey={ticket.imageObjectKey}
            imageUrl={ticket.imageUrl}
            category={ticket.category}
            alt={t('ticket.photoAlt', { ticketNumber: ticket.ticketNumber })}
          />
          <p className="ticket-preview__description">{ticket.description}</p>
          <p className="ticket-preview__location">{ticket.location.addressText}</p>
        </section>

        <section className="ticket-preview__section">
          <h3 className="ticket-preview__section-title">{t('ticket.preview.publicFeed')}</h3>
          <p className="ticket-preview__hint">{t('ticket.preview.publicHint')}</p>
          <label className="ticket-preview__field">
            <span>{t('ticket.preview.publicDescription')}</span>
            <textarea
              value={publicDescription}
              onChange={(event) => setPublicDescription(event.target.value)}
              rows={3}
              disabled={isSavingPublic}
            />
          </label>
          <label className="ticket-preview__field">
            <span>{t('ticket.preview.publicLocation')}</span>
            <input
              type="text"
              value={publicLocationLabel}
              onChange={(event) => setPublicLocationLabel(event.target.value)}
              placeholder={t('ticket.preview.publicLocationPlaceholder')}
              disabled={isSavingPublic}
            />
          </label>
          <ImagePrivacyStatus redaction={ticket.imageRedaction} />
          <p className="ticket-preview__meta">
            {t('ticket.preview.publicStatus', { status: ticket.public?.status ?? 'DRAFT' })}
            {ticket.public?.imageObjectKey
              ? t('ticket.preview.photoApproved')
              : t('ticket.preview.noPublicPhoto')}
          </p>
          <div className="ticket-preview__row">
            <button
              type="button"
              className="ticket-preview__btn ticket-preview__btn--primary"
              onClick={() => void handleSavePublicContent('PUBLISHED')}
              disabled={isSavingPublic || !publicDescription.trim() || !publicLocationLabel.trim()}
            >
              {isSavingPublic ? t('ticket.preview.saving') : t('ticket.preview.publish')}
            </button>
            <button
              type="button"
              className="ticket-preview__btn"
              onClick={() => void handleSavePublicContent('UNPUBLISHED')}
              disabled={isSavingPublic || (ticket.public?.status ?? 'DRAFT') === 'DRAFT'}
            >
              {t('ticket.preview.unpublish')}
            </button>
          </div>
        </section>

        {actionNotice?.tone === 'error' ? (
          <p className="ticket-preview__error" role="alert">
            {'key' in actionNotice ? t(actionNotice.key) : actionNotice.text}
          </p>
        ) : null}
        {actionNotice?.tone === 'success' ? (
          <p className="ticket-preview__success" role="status">
            {'key' in actionNotice ? t(actionNotice.key) : actionNotice.text}
          </p>
        ) : null}
      </div>

      <footer className="ticket-preview__footer">
        <Link to={`/tickets/${ticket.ticketId}`} className="ticket-preview__open">
          {t('ticket.preview.openFull')}
        </Link>
      </footer>
    </aside>
  );
}
