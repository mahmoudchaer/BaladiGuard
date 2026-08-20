"""Department routing services."""

from app.services.routing.department_map import (
    category_to_department_map,
    department_id_for_category,
    department_ids,
    department_name,
    load_department_catalog,
    suggest_department_id,
)
from app.services.routing.municipality_router import (
    eligible_municipalities,
    route_ticket_to_municipality,
    service_domain_for_category,
)

__all__ = [
    "category_to_department_map",
    "department_id_for_category",
    "department_ids",
    "department_name",
    "eligible_municipalities",
    "load_department_catalog",
    "route_ticket_to_municipality",
    "service_domain_for_category",
    "suggest_department_id",
]
