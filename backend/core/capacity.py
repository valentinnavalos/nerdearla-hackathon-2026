"""Live slots: how many rooms may hold a Gemini Live session at once.

MAX_CONCURRENT_LIVE is an operational safety limit of this backend, not a limit published by
Gemini (see docs/CONCURRENCY-REPORT.md for what is documented, observed and decided)."""


class CapacityError(RuntimeError):
    """No free Live slot: the room is not started (the API answers 409)."""


class CapacityGuard:
    """Slot registry keyed by room. reserve() never waits: a full guard raises at once, so a
    third room gets a clear error instead of hanging until another one stops.

    Everything runs on one event loop and nothing here awaits, so check + reserve is atomic."""

    def __init__(self, max_slots: int):
        self.max_slots = max_slots
        self._rooms: set[str] = set()

    def reserve(self, room_id: str) -> None:
        """Take a slot for `room_id`. A room that already holds one keeps it (rotation, reconnect)."""
        if room_id in self._rooms:
            return
        if len(self._rooms) >= self.max_slots:
            raise CapacityError(
                f"cupo Live lleno ({len(self._rooms)}/{self.max_slots}): "
                "pará otra sala o subí MAX_CONCURRENT_LIVE"
            )
        self._rooms.add(room_id)

    def release(self, room_id: str) -> None:
        self._rooms.discard(room_id)

    def holds(self, room_id: str) -> bool:
        return room_id in self._rooms

    def usage(self) -> dict[str, int]:
        return {"used": len(self._rooms), "max": self.max_slots}
