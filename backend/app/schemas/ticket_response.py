from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.ai_processing import AiProcessingStatus
from app.schemas.stored_ticket import PublicTicketStatus
from app.schemas.ticket import ReportContact, ReportLocation
from app.schemas.ticket_status import TicketStatus

TicketPriority = Literal["low", "medium", "high", "critical"]


class TicketImageReference(BaseModel):
    object_key: str = Field(alias="objectKey")
    url: str | None = None
    content_type: str | None = Field(default=None, alias="contentType")
    created_at: str | None = Field(default=None, alias="createdAt")

    model_config = {"populate_by_name": True}


class TicketDepartment(BaseModel):
    department_id: str | None = Field(default=None, alias="departmentId")
    name: str | None = None

    model_config = {"populate_by_name": True}


class TicketAiFields(BaseModel):
    original_description: str | None = Field(default=None, alias="originalDescription")
    cleaned_description: str | None = Field(default=None, alias="cleanedDescription")
    ai_suggested_category: str | None = Field(default=None, alias="aiSuggestedCategory")
    ai_category_explanation: str | None = Field(default=None, alias="aiCategoryExplanation")
    ai_confidence: float | None = Field(default=None, alias="aiConfidence")
    final_category: str | None = Field(default=None, alias="finalCategory")
    category_reviewed_by: str | None = Field(default=None, alias="categoryReviewedBy")
    category_reviewed_at: str | None = Field(default=None, alias="categoryReviewedAt")
    ai_processing_status: AiProcessingStatus | None = Field(
        default=None,
        alias="aiProcessingStatus",
    )
    ai_model_version: str | None = Field(default=None, alias="aiModelVersion")
    suggested_category: str | None = Field(default=None, alias="suggestedCategory")
    urgency_score: int | None = Field(default=None, alias="urgencyScore", ge=0, le=100)
    urgency_reason: str | None = Field(default=None, alias="urgencyReason")
    summary: str | None = None
    suggested_department_id: str | None = Field(default=None, alias="suggestedDepartmentId")

    model_config = {"populate_by_name": True}


class TicketStatusHistoryEntry(BaseModel):
    status: TicketStatus
    changed_at: str = Field(alias="changedAt")
    changed_by: str | None = Field(default=None, alias="changedBy")
    note: str | None = None

    model_config = {"populate_by_name": True}


class TicketAuditHistoryEntry(BaseModel):
    """Staff-only audit entry for ticket mutations (issues #143 / #181)."""

    action_type: Literal[
        "STATUS_CHANGE",
        "CATEGORY_REVIEW",
        "DEPARTMENT_ASSIGN",
        "DUPLICATE_MERGE",
        "PUBLIC_CONTENT_UPDATE",
    ] = Field(alias="actionType")
    actor_id: str | None = Field(default=None, alias="actorId")
    actor_role: Literal["municipal_staff", "administrator"] | None = Field(
        default=None,
        alias="actorRole",
    )
    summary: str
    previous_value: str | None = Field(default=None, alias="previousValue")
    new_value: str | None = Field(default=None, alias="newValue")
    changed_at: str = Field(alias="changedAt")

    model_config = {"populate_by_name": True}


class CitizenTicketLocation(BaseModel):
    address_text: str = Field(alias="addressText")

    model_config = {"populate_by_name": True}


class CitizenTicketDepartment(BaseModel):
    """Citizen-safe department display; never exposes internal department IDs."""

    name: str


class CitizenTicketTimelineEntry(BaseModel):
    status: TicketStatus
    changed_at: str = Field(alias="changedAt")

    model_config = {"populate_by_name": True}


class CitizenTicketResponse(BaseModel):
    """Citizen-safe ticket tracking response returned by public tracking-code lookup."""

    ticket_number: str | None = Field(default=None, alias="ticketNumber")
    tracking_code: str = Field(alias="trackingCode")
    status: TicketStatus
    category: str | None = None
    location: CitizenTicketLocation | None = None
    department: CitizenTicketDepartment | None = None
    created_at: str = Field(alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")
    last_updated_at: str = Field(alias="lastUpdatedAt")
    timeline: list[CitizenTicketTimelineEntry] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class PublicTicketAttribution(BaseModel):
    display_name: str = Field(alias="displayName")
    is_named: bool = Field(alias="isNamed")

    model_config = {"populate_by_name": True}


class PublicTicketMapLocation(BaseModel):
    address_text: str = Field(alias="addressText")
    latitude: float
    longitude: float

    model_config = {"populate_by_name": True}


class PublicTicketResponse(BaseModel):
    """Citizen-safe public browsing projection. Never includes tracking codes or IDs."""

    ticket_number: str = Field(alias="ticketNumber")
    status: TicketStatus
    category: str | None = None
    description: str
    location: CitizenTicketLocation
    map_location: PublicTicketMapLocation = Field(alias="mapLocation")
    department: CitizenTicketDepartment | None = None
    attribution: PublicTicketAttribution
    # Optional time-limited URL for a staff-approved public photo only.
    # Absent/null when publicImageObjectKey is unset; never derived from raw uploads.
    photo_url: str | None = Field(default=None, alias="photoUrl")
    created_at: str = Field(alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")

    model_config = {"populate_by_name": True}


class PublicTicketListResponse(BaseModel):
    items: list[PublicTicketResponse]
    next_cursor: str | None = Field(default=None, alias="nextCursor")
    limit: int = Field(ge=1, le=50)

    model_config = {"populate_by_name": True}


class TicketDuplicateReference(BaseModel):
    duplicate_group_id: str = Field(alias="duplicateGroupId")
    ticket_ids: list[str] | None = Field(default=None, alias="ticketIds")
    canonical_ticket_id: str | None = Field(default=None, alias="canonicalTicketId")

    model_config = {"populate_by_name": True}


class TicketDuplicateSuggestion(BaseModel):
    ticket_id: str = Field(alias="ticketId")
    ticket_number: str | None = Field(default=None, alias="ticketNumber")
    distance_meters: float = Field(alias="distanceMeters")
    status: TicketStatus
    category: str
    score: float | None = None
    category_match: Literal["same", "similar"] | None = Field(default=None, alias="categoryMatch")

    model_config = {"populate_by_name": True}


class UpdateTicketStatusRequest(BaseModel):
    status: TicketStatus
    updated_by: str | None = Field(default=None, alias="updatedBy", max_length=120)
    note: str | None = Field(default=None, max_length=500)

    model_config = {"populate_by_name": True}


class UpdateTicketPublicContentRequest(BaseModel):
    """Staff-approved public projection fields, including optional public photo approval.

    Public photos may only be approved from this ticket's own ``imageObjectKey`` or cleared.
    Arbitrary/unbound object keys are rejected (``extra='forbid'``).
    """

    public_status: PublicTicketStatus = Field(alias="publicStatus")
    public_description: str = Field(default="", alias="publicDescription", max_length=2000)
    public_location_label: str = Field(default="", alias="publicLocationLabel", max_length=200)
    approve_original_photo: bool = Field(default=False, alias="approveOriginalPhoto")
    clear_public_photo: bool = Field(default=False, alias="clearPublicPhoto")
    updated_by: str | None = Field(default=None, alias="updatedBy", max_length=120)

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @model_validator(mode="after")
    def validate_photo_modes(self) -> "UpdateTicketPublicContentRequest":
        if self.approve_original_photo and self.clear_public_photo:
            raise ValueError("Cannot both approve and clear the public photo in one request.")
        return self


class TicketPublicFields(BaseModel):
    """Staff-visible public projection state (never exposed on citizen tracking)."""

    status: PublicTicketStatus
    description: str | None = None
    location_label: str | None = Field(default=None, alias="locationLabel")
    image_object_key: str | None = Field(default=None, alias="imageObjectKey")
    published_at: str | None = Field(default=None, alias="publishedAt")

    model_config = {"populate_by_name": True}


class TicketResponse(BaseModel):
    """Shared ticket read shape returned by staff dashboard and ticket read APIs."""

    ticket_id: str = Field(alias="ticketId")
    ticket_number: str | None = Field(default=None, alias="ticketNumber")
    tracking_code: str = Field(alias="trackingCode")
    description: str
    contact: ReportContact | None = None
    owner_user_id: str | None = Field(default=None, alias="ownerUserId")
    category: str
    priority: TicketPriority | None
    status: TicketStatus
    location: ReportLocation
    image_references: list[TicketImageReference] = Field(alias="imageReferences")
    image_object_key: str | None = Field(default=None, alias="imageObjectKey")
    department: TicketDepartment | None
    department_id: str | None = Field(default=None, alias="departmentId")
    created_by: str | None = Field(default=None, alias="createdBy")
    municipality_id: str | None = Field(default=None, alias="municipalityId")
    duplicate_group_id: str | None = Field(default=None, alias="duplicateGroupId")
    created_at: str = Field(alias="createdAt")
    updated_at: str | None = Field(alias="updatedAt")
    updated_by: str | None = Field(default=None, alias="updatedBy")
    ai: TicketAiFields | None = None
    public: TicketPublicFields | None = None
    status_history: list[TicketStatusHistoryEntry] | None = Field(
        default=None,
        alias="statusHistory",
    )
    audit_history: list[TicketAuditHistoryEntry] = Field(
        default_factory=list,
        alias="auditHistory",
    )
    duplicate_group: TicketDuplicateReference | None = Field(
        default=None,
        alias="duplicateGroup",
    )
    duplicate_suggestions: list[TicketDuplicateSuggestion] = Field(
        default_factory=list,
        alias="duplicateSuggestions",
    )

    model_config = {"populate_by_name": True}
