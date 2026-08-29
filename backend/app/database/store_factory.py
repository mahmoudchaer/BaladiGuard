from app.config import Settings, get_settings
from app.database import content_safety_job_store as content_safety_job_store_module
from app.database import redaction_job_store as redaction_job_store_module
from app.database.account_audit_store import AccountAuditStore
from app.database.ai_job_store import AiJobStore
from app.database.audit_history_store import AuditHistoryStore
from app.database.citizen_store import CitizenStore
from app.database.duplicate_group_store import DuplicateGroupStore
from app.database.memory import ticket_store
from app.database.memory_account_audit import account_audit_store
from app.database.memory_ai_job import ai_job_store
from app.database.memory_audit_history import audit_history_store
from app.database.memory_citizen import citizen_store
from app.database.memory_citizen_otp import citizen_otp_store
from app.database.memory_citizen_session import citizen_session_store
from app.database.memory_content_safety_job import content_safety_job_store
from app.database.memory_department import department_store
from app.database.memory_duplicate_group import duplicate_group_store
from app.database.memory_municipality import municipality_store
from app.database.memory_notification_delivery import notification_delivery_store
from app.database.memory_ops import ops_alert_ack_store, ops_audit_store, ops_error_store
from app.database.memory_privacy_request import privacy_request_audit_store
from app.database.memory_redaction_job import redaction_job_store
from app.database.memory_rewards import rewards_ledger_store, rewards_projection_store
from app.database.memory_staff import staff_store
from app.database.memory_staff_comments import staff_comment_store
from app.database.memory_staff_password_reset import staff_password_reset_store
from app.database.memory_status_history import status_history_store
from app.database.notification_delivery_store import NotificationDeliveryStore
from app.database.resolution_review_store import ResolutionReviewStore
from app.database.staff_comment_store import StaffCommentStore
from app.database.staff_store import StaffStore
from app.database.status_history_store import StatusHistoryStore
from app.database.ticket_store import TicketStore
from app.database.work_order_evidence_store import WorkOrderEvidenceStore
from app.database.work_order_store import WorkOrderStore
from app.database.workforce_store import WorkforceStore


def build_ticket_store(settings: Settings | None = None) -> TicketStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_ticket_store import DynamoTicketStore

        return DynamoTicketStore(settings)
    return ticket_store


def build_ai_job_store(settings: Settings | None = None) -> AiJobStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_ai_job_store import DynamoAiJobStore

        return DynamoAiJobStore(settings)
    return ai_job_store


def build_redaction_job_store(
    settings: Settings | None = None,
) -> redaction_job_store_module.RedactionJobStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_redaction_job_store import DynamoRedactionJobStore

        return DynamoRedactionJobStore(settings)
    return redaction_job_store


def build_status_history_store(settings: Settings | None = None) -> StatusHistoryStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_status_history_store import DynamoStatusHistoryStore

        return DynamoStatusHistoryStore(settings)
    return status_history_store


def build_audit_history_store(settings: Settings | None = None) -> AuditHistoryStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_audit_history_store import DynamoAuditHistoryStore

        return DynamoAuditHistoryStore(settings)
    return audit_history_store


def build_account_audit_store(settings: Settings | None = None) -> AccountAuditStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_account_audit_store import DynamoAccountAuditStore

        return DynamoAccountAuditStore(settings)
    return account_audit_store


def build_notification_delivery_store(
    settings: Settings | None = None,
) -> NotificationDeliveryStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_notification_delivery_store import (
            DynamoNotificationDeliveryStore,
        )

        return DynamoNotificationDeliveryStore(settings)
    return notification_delivery_store


def build_duplicate_group_store(settings: Settings | None = None) -> DuplicateGroupStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_duplicate_group_store import DynamoDuplicateGroupStore

        return DynamoDuplicateGroupStore(settings)
    return duplicate_group_store


def build_citizen_store(settings: Settings | None = None) -> CitizenStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_citizen_store import DynamoCitizenStore

        return DynamoCitizenStore(settings)
    return citizen_store


def build_citizen_session_store(settings: Settings | None = None):
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_citizen_session import DynamoCitizenSessionStore

        return DynamoCitizenSessionStore(settings)
    return citizen_session_store


def build_citizen_otp_store(settings: Settings | None = None):
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_citizen_otp import DynamoCitizenOtpStore

        return DynamoCitizenOtpStore(settings)
    return citizen_otp_store


def build_staff_store(settings: Settings | None = None) -> StaffStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_staff_store import DynamoStaffStore

        return DynamoStaffStore(settings)
    return staff_store


def build_staff_comment_store(settings: Settings | None = None) -> StaffCommentStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_staff_comment_store import DynamoStaffCommentStore

        return DynamoStaffCommentStore(settings)
    return staff_comment_store


def build_workforce_store(settings: Settings | None = None) -> WorkforceStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_workforce_store import DynamoWorkforceStore

        return DynamoWorkforceStore(settings)
    from app.database.memory_workforce import workforce_store

    return workforce_store


def build_work_order_store(settings: Settings | None = None) -> WorkOrderStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_work_order_store import DynamoWorkOrderStore

        return DynamoWorkOrderStore(settings)
    from app.database.memory_work_order import work_order_store

    return work_order_store


def build_staff_password_reset_store(settings: Settings | None = None):
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_staff_password_reset import DynamoStaffPasswordResetStore

        return DynamoStaffPasswordResetStore(settings)
    return staff_password_reset_store


def get_ticket_store() -> TicketStore:
    return build_ticket_store(get_settings())


def get_ai_job_store() -> AiJobStore:
    return build_ai_job_store(get_settings())


def get_redaction_job_store() -> redaction_job_store_module.RedactionJobStore:
    return build_redaction_job_store(get_settings())


def build_content_safety_job_store(
    settings: Settings | None = None,
) -> content_safety_job_store_module.ContentSafetyJobStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_content_safety_job_store import DynamoContentSafetyJobStore

        return DynamoContentSafetyJobStore(settings)
    return content_safety_job_store


def get_content_safety_job_store() -> content_safety_job_store_module.ContentSafetyJobStore:
    return build_content_safety_job_store(get_settings())


def get_status_history_store() -> StatusHistoryStore:
    return build_status_history_store(get_settings())


def get_audit_history_store() -> AuditHistoryStore:
    return build_audit_history_store(get_settings())


def get_account_audit_store() -> AccountAuditStore:
    return build_account_audit_store(get_settings())


def get_notification_delivery_store() -> NotificationDeliveryStore:
    return build_notification_delivery_store(get_settings())


def get_duplicate_group_store() -> DuplicateGroupStore:
    return build_duplicate_group_store(get_settings())


def get_citizen_store() -> CitizenStore:
    return build_citizen_store(get_settings())


def get_citizen_session_store():
    return build_citizen_session_store(get_settings())


def get_citizen_otp_store():
    return build_citizen_otp_store(get_settings())


def get_staff_store() -> StaffStore:
    return build_staff_store(get_settings())


def get_staff_comment_store() -> StaffCommentStore:
    return build_staff_comment_store(get_settings())


def get_staff_password_reset_store():
    return build_staff_password_reset_store(get_settings())


def get_workforce_store() -> WorkforceStore:
    return build_workforce_store(get_settings())


def get_work_order_store() -> WorkOrderStore:
    return build_work_order_store(get_settings())


def build_work_order_evidence_store(settings: Settings | None = None) -> WorkOrderEvidenceStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_work_order_evidence_store import DynamoWorkOrderEvidenceStore

        return DynamoWorkOrderEvidenceStore(settings)
    from app.database.memory_work_order_evidence import work_order_evidence_store

    return work_order_evidence_store


def get_work_order_evidence_store() -> WorkOrderEvidenceStore:
    return build_work_order_evidence_store(get_settings())


def build_resolution_review_store(settings: Settings | None = None) -> ResolutionReviewStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_resolution_review_store import DynamoResolutionReviewStore

        return DynamoResolutionReviewStore(settings)
    from app.database.memory_resolution_review import resolution_review_store

    return resolution_review_store


def get_resolution_review_store() -> ResolutionReviewStore:
    return build_resolution_review_store(get_settings())


def build_ops_alert_ack_store(settings: Settings | None = None):
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_ops_store import DynamoOpsAlertAckStore

        return DynamoOpsAlertAckStore(settings)
    return ops_alert_ack_store


def build_ops_error_store(settings: Settings | None = None):
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_ops_store import DynamoOpsErrorStore

        return DynamoOpsErrorStore(settings)
    return ops_error_store


def build_ops_audit_store(settings: Settings | None = None):
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_ops_store import DynamoOpsAuditStore

        return DynamoOpsAuditStore(settings)
    return ops_audit_store


def get_ops_alert_ack_store():
    return build_ops_alert_ack_store(get_settings())


def get_ops_error_store():
    return build_ops_error_store(get_settings())


def get_ops_audit_store():
    return build_ops_audit_store(get_settings())


def build_privacy_request_audit_store(settings: Settings | None = None):
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_privacy_request import DynamoPrivacyRequestAuditStore

        return DynamoPrivacyRequestAuditStore(settings)
    return privacy_request_audit_store


def get_privacy_request_audit_store():
    return build_privacy_request_audit_store(get_settings())


def build_municipality_store(settings: Settings | None = None):
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_municipality_store import DynamoMunicipalityStore

        return DynamoMunicipalityStore(settings)
    return municipality_store


def get_municipality_store():
    return build_municipality_store(get_settings())


def build_department_store(settings: Settings | None = None):
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_department_store import DynamoDepartmentStore

        return DynamoDepartmentStore(settings)
    return department_store


def get_department_store():
    return build_department_store(get_settings())


def build_whatsapp_conversation_store(settings: Settings | None = None):
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_whatsapp_store import DynamoWhatsAppConversationStore

        return DynamoWhatsAppConversationStore(settings)
    from app.database.memory_whatsapp import whatsapp_conversation_store

    return whatsapp_conversation_store


def get_whatsapp_conversation_store():
    return build_whatsapp_conversation_store(get_settings())


def build_whatsapp_dedup_store(settings: Settings | None = None):
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_whatsapp_store import DynamoWhatsAppDedupStore

        return DynamoWhatsAppDedupStore(settings)
    from app.database.memory_whatsapp import whatsapp_dedup_store

    return whatsapp_dedup_store


def get_whatsapp_dedup_store():
    return build_whatsapp_dedup_store(get_settings())


def build_rewards_ledger_store(settings: Settings | None = None):
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_rewards_store import DynamoRewardsLedgerStore

        return DynamoRewardsLedgerStore(settings)
    return rewards_ledger_store


def build_rewards_projection_store(settings: Settings | None = None):
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_rewards_store import DynamoRewardsProjectionStore

        return DynamoRewardsProjectionStore(settings)
    return rewards_projection_store


def get_rewards_ledger_store():
    return build_rewards_ledger_store(get_settings())


def get_rewards_projection_store():
    return build_rewards_projection_store(get_settings())
