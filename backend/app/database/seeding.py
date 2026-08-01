import json
import re
from decimal import Decimal
from pathlib import Path

from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamo_ticket_store import TICKET_NUMBER_COUNTER_ID
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.serialization import prepare_dynamodb_value

REPO_ROOT = Path(__file__).resolve().parents[3]
SEEDS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "db" / "seeds"
MOCK_TICKETS_PATH = REPO_ROOT / "mock_tickets.json"


def load_json_seed(filename: str) -> list[dict]:
    return json.loads((SEEDS_DIR / filename).read_text(encoding="utf-8"))


def put_items(table, items: list[dict]) -> int:
    for item in items:
        table.put_item(Item=prepare_dynamodb_value(item))
    return len(items)


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
    tickets_table = resource.Table(build_table_name(prefix, "tickets"))
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
        sample_tickets = json.loads(MOCK_TICKETS_PATH.read_text(encoding="utf-8"))
        ticket_count = put_items(tickets_table, sample_tickets)
        counter_seed_value = max_ticket_sequence_from_samples(sample_tickets)
        print(f"Seeded sample tickets: {ticket_count}")
    else:
        print("Skipped sample tickets (set SEED_SAMPLE_TICKETS=true to load mock_tickets.json).")

    initialize_ticket_counter(counters_table, counter_seed_value)
