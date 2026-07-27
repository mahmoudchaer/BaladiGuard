"""Department routing services."""

from app.services.routing.department_map import (
    category_to_department_map,
    department_id_for_category,
    department_ids,
    department_name,
    load_department_catalog,
    suggest_department_id,
)

__all__ = [
    "category_to_department_map",
    "department_id_for_category",
    "department_ids",
    "department_name",
    "load_department_catalog",
    "suggest_department_id",
]
