import json
import re
from decimal import Decimal
from pathlib import Path

from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamo_ticket_store import TICKET_NUMBER_COUNTER_ID
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import prepare_dynamodb_value, ticket_to_item
from app.schemas.stored_duplicate_group import StoredDuplicateGroup
from app.schemas.stored_status_history import StoredStatusHistory
from app.schemas.stored_ticket import StoredTicket
from app.schemas.ticket_status import TicketStatus
from app.utils.phone import phone_claim_key

REPO_ROOT = Path(__file__).resolve().parents[3]
SEEDS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "db" / "seeds"
MOCK_TICKETS_PATH = REPO_ROOT / "mock_tickets.json"

STATUS_PROGRESSIONS: dict[TicketStatus, list[TicketStatus]] = {
    "SUBMITTED": ["SUBMITTED"],
    "UNDER_REVIEW": ["SUBMITTED", "UNDER_REVIEW"],
    "ASSIGNED": ["SUBMITTED", "UNDER_REVIEW", "ASSIGNED"],
    "IN_PROGRESS": ["SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS"],
    "RESOLVED": ["SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS", "RESOLVED"],
    "CLOSED": ["SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED"],
}


def load_json_seed(filename: str) -> list[dict]:
    return json.loads((SEEDS_DIR / filename).read_text(encoding="utf-8"))


def put_items(table, items: list[dict]) -> int:
    for item in items:
        table.put_item(Item=prepare_dynamodb_value(item))
    return len(items)


def seed_citizens(users_table, phone_claims_table, citizens: list[dict]) -> int:
    for citizen in citizens:
        users_table.put_item(Item=prepare_dynamodb_value(citizen))
        phone_claims_table.put_item(
            Item={
                "phoneKey": phone_claim_key(citizen["phone"]),
                "userId": citizen["userId"],
                "createdAt": citizen["phoneVerifiedAt"],
            }
        )
    return len(citizens)


def seed_sample_tickets(tickets_table, sample_tickets: list[dict]) -> int:
    for item in sample_tickets:
        tickets_table.put_item(Item=ticket_to_item(StoredTicket.model_validate(item)))
    return len(sample_tickets)


def build_duplicate_group_items(sample_tickets: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for ticket in sample_tickets:
        group_id = ticket.get("duplicateGroupId")
        if isinstance(group_id, str) and group_id.strip():
            groups.setdefault(group_id, []).append(ticket)

    items: list[dict] = []
    for group_id, tickets in groups.items():
        ordered = sorted(tickets, key=lambda ticket: ticket["createdAt"])
        group = StoredDuplicateGroup(
            duplicateGroupId=group_id,
            canonicalTicketId=ordered[0]["ticketId"],
            ticketIds=[ticket["ticketId"] for ticket in ordered],
            createdAt=ordered[0]["updatedAt"],
            createdBy=ordered[0].get("categoryReviewedBy") or ordered[0].get("createdBy"),
        )
        items.append(group.model_dump(by_alias=True, mode="json"))
    return items


def build_status_history_items(sample_tickets: list[dict]) -> list[dict]:
    items: list[dict] = []
    for ticket in sample_tickets:
        previous_status: TicketStatus | None = None
        progression = STATUS_PROGRESSIONS[StoredTicket.model_validate(ticket).status]
        for index, status in enumerate(progression):
            created_at = ticket["createdAt"] if index == 0 else ticket["updatedAt"]
            updated_by = None if status == "SUBMITTED" else ticket.get("categoryReviewedBy")
            entry = StoredStatusHistory(
                historyId=f"hist_{ticket['ticketNumber'].lower().replace('-', '_')}_{index + 1}",
                ticketId=ticket["ticketId"],
                previousStatus=previous_status,
                newStatus=status,
                updatedBy=updated_by,
                note=_status_history_note(status),
                createdAt=created_at,
            )
            items.append(entry.model_dump(by_alias=True, mode="json"))
            previous_status = status
    return items


def _status_history_note(status: TicketStatus) -> str:
    notes = {
        "SUBMITTED": "Demo report submitted by a verified citizen.",
        "UNDER_REVIEW": "Demo staff triage started.",
        "ASSIGNED": "Demo report assigned to the responsible department.",
        "IN_PROGRESS": "Demo department work is in progress.",
        "RESOLVED": "Demo report marked resolved.",
        "CLOSED": "Demo report closed after follow-up.",
    }
    return notes[status]


def initialize_ticket_counter(counters_table, value: int) -> None:
    try:
        counters_table.put_item(
            Item={
                "counterId": TICKET_NUMBER_COUNTER_ID,
                "value": Decimal(value),
            },
            ConditionExpression="attribute_not_exists(counterId)",
        )
        print(f"Initialized ticket counter at {value}.")
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            print("Ticket counter already exists; leaving current value unchanged.")
            return
        raise


def max_ticket_sequence_from_samples(tickets: list[dict]) -> int:
    highest = 0
    pattern = re.compile(r"-(\d+)$")
    for ticket in tickets:
        ticket_number = ticket.get("ticketNumber", "")
        match = pattern.search(ticket_number)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest


def run_seed(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    prefix = settings.dynamodb_table_prefix
    resource = create_dynamodb_resource(settings)

    municipalities_table = resource.Table(build_table_name(prefix, "municipalities"))
    departments_table = resource.Table(build_table_name(prefix, "departments"))
    categories_table = resource.Table(build_table_name(prefix, "categories"))
    users_table = resource.Table(build_table_name(prefix, "users"))
    phone_claims_table = resource.Table(build_table_name(prefix, "phone-claims"))
    tickets_table = resource.Table(build_table_name(prefix, "tickets"))
    duplicate_groups_table = resource.Table(build_table_name(prefix, "duplicate-groups"))
    status_history_table = resource.Table(build_table_name(prefix, "ticket-status-history"))
    counters_table = resource.Table(build_table_name(prefix, "counters"))

    municipality_count = put_items(municipalities_table, load_json_seed("municipalities.json"))
    department_count = put_items(departments_table, load_json_seed("departments.json"))
    category_count = put_items(categories_table, load_json_seed("categories.json"))

    print(f"Seeded municipalities: {municipality_count}")
    print(f"Seeded departments: {department_count}")
    print(f"Seeded categories: {category_count}")

    from app.database.dynamo_staff_store import DynamoStaffStore
    from app.services.staff.bootstrap import ensure_demo_staff_accounts

    staff_created = ensure_demo_staff_accounts(
        DynamoStaffStore(settings),
        settings=settings,
    )
    print(f"Seeded demo staff accounts created: {staff_created}")

    counter_seed_value = 0
    if settings.seed_sample_tickets:
        citizen_count = seed_citizens(
            users_table,
            phone_claims_table,
            load_json_seed("citizens.json"),
        )
        sample_tickets = json.loads(MOCK_TICKETS_PATH.read_text(encoding="utf-8"))
        ticket_count = seed_sample_tickets(tickets_table, sample_tickets)
        duplicate_group_count = put_items(
            duplicate_groups_table,
            build_duplicate_group_items(sample_tickets),
        )
        history_count = put_items(status_history_table, build_status_history_items(sample_tickets))
        counter_seed_value = max_ticket_sequence_from_samples(sample_tickets)
        print(f"Seeded demo citizens: {citizen_count}")
        print(f"Seeded sample tickets: {ticket_count}")
        print(f"Seeded sample duplicate groups: {duplicate_group_count}")
        print(f"Seeded sample status history entries: {history_count}")
    else:
        print("Skipped sample tickets (set SEED_SAMPLE_TICKETS=true to load mock_tickets.json).")

    initialize_ticket_counter(counters_table, counter_seed_value)
