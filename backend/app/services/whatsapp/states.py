"""Deterministic conversation states for WhatsApp report intake (issue #296)."""

from __future__ import annotations

from typing import Literal

ConversationState = Literal[
    "welcome",
    "language",
    "description",
    "location",
    "photo",
    "optional_name",
    "review",
    "submitting",
    "completed",
    "cancelled",
    "expired",
]

EDITABLE_STATES: tuple[ConversationState, ...] = (
    "welcome",
    "language",
    "description",
    "location",
    "photo",
    "optional_name",
    "review",
)

FORWARD_FLOW: tuple[ConversationState, ...] = (
    "welcome",
    "language",
    "description",
    "location",
    "photo",
    "optional_name",
    "review",
    "submitting",
    "completed",
)

COMMANDS = frozenset({"back", "cancel", "restart", "help"})

SUPPORTED_LANGUAGES = frozenset({"en", "ar"})


def previous_editable_state(state: ConversationState) -> ConversationState | None:
    if state not in EDITABLE_STATES:
        return None
    index = EDITABLE_STATES.index(state)
    if index <= 0:
        return None
    return EDITABLE_STATES[index - 1]


def next_forward_state(state: ConversationState) -> ConversationState | None:
    if state not in FORWARD_FLOW:
        return None
    index = FORWARD_FLOW.index(state)
    if index >= len(FORWARD_FLOW) - 1:
        return None
    return FORWARD_FLOW[index + 1]


def parse_command(text: str | None) -> str | None:
    if not text:
        return None
    normalized = text.strip().casefold()
    if normalized in COMMANDS:
        return normalized
    # Arabic short aliases for deterministic commands (not AI intent).
    aliases = {
        "رجوع": "back",
        "الغاء": "cancel",
        "إلغاء": "cancel",
        "اعادة": "restart",
        "إعادة": "restart",
        "مساعدة": "help",
    }
    return aliases.get(normalized)
