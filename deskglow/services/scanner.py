"""Discovery: list the BLE devices advertising nearby."""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Advert:
    """One advertising device, as plain data."""

    address: str
    name: str | None = None
    rssi: int | None = None
    service_uuids: list[str] = field(default_factory=list)


class Scanner(Protocol):
    async def scan(self, timeout: float) -> list[Advert]:
        """Scan for `timeout` seconds and return every device seen."""
