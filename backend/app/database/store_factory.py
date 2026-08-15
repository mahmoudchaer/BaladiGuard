from app.config import Settings, get_settings
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
from app.database.memory_duplicate_group import duplicate_group_store
from app.database.memory_notification_delivery import notification_delivery_store
from app.database.memory_redaction_job import redaction_job_store
from app.database.memory_staff import staff_store
from app.database.memory_staff_comments import staff_comment_store
from app.database.memory_staff_password_reset import staff_password_reset_store
from app.database.memory_status_history import status_history_store
from app.database.notification_delivery_store import NotificationDeliveryStore
from app.database.staff_comment_store import StaffCommentStore
from app.database.staff_store import StaffStore
from app.database.status_history_store import StatusHistoryStore
from app.database.ticket_store import TicketStore
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
