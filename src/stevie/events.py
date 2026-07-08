from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(slots=True, frozen=True)
class StevieEvent:
    topic: str
    source: str
    payload: Any
    
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    event_id: str = field(
        default_factory=lambda: str(uuid4())
    )
