import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from domain.value_objects import Augenzahl, Spielername


@dataclass
class Wurf:
    """
    Entity: represents a single dice throw — a unique event in time.

    WHY is this an Entity and not a Value Object?
    Two throws that both result in 4 are NOT the same throw.
    Each throw has its own identity: unique ID and timestamp.

    Identity = ID (not the value of augenzahl)
    """

    # The result of this throw — a Value Object, not a plain int
    # This way the 1-6 rule is always guaranteed
    augenzahl: Augenzahl

    # When did this throw happen?
    # field(default_factory=...) means: call datetime.now() at the moment
    # of object creation, not when the class is defined
    zeitstempel: datetime = field(default_factory=datetime.now)

    # The unique identity of this throw
    # lambda: str(uuid.uuid4()) generates a new UUID every time a Wurf is created
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Which player made this throw? Optional for legacy or non-player throws.
    spieler_id: str | None = None

    def __repr__(self):
        owner = f" by {self.spieler_id[:8]}..." if self.spieler_id else ""
        return (
            f"Throw #{self.id[:8]}... | "
            f"Result: {self.augenzahl} | "
            f"At: {self.zeitstempel.strftime('%H:%M:%S')}" + owner
        )


@dataclass
class Spieler:
    """
    Entity: represents a player in the game with their throws history.

    Design: This is a PASSIVE data holder.
    - Stores the player's name and their throws (read-only)
    - Provides read-only statistical queries
    - DOES NOT modify its own state directly

    WHY this design?
    - The Aggregate Root (Wuerfelspiel) controls all state changes
    - Consistency and event sourcing are guaranteed at the aggregate level
    - Spieler is just data + read-only calculations

    Identity = ID (not the name)
    """

    # The player's name — a Value Object
    name: Spielername

    # This player's throws — each Wurf has its own identity
    # MODIFIED ONLY by the Aggregate Root, never directly by Spieler
    wuerfe: List[Wurf] = field(default_factory=list)

    # The unique identity of this player
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def anzahl_wuerfe(self) -> int:
        """
        Read-only: Return the total number of throws by this player.
        This method does NOT modify state.
        """
        return len(self.wuerfe)

    def statistik(self) -> dict[int, int]:
        """
        Read-only: Compute throw frequency for each face value (1-6) for this player.
        This method does NOT modify state.

        Returns:
            {1: 5, 2: 3, 3: 4, ...} for example
        """
        stats = {i: 0 for i in range(1, 7)}
        for wurf in self.wuerfe:
            stats[wurf.augenzahl.wert] += 1
        return stats

    def punkte(self) -> int:
        return sum(wurf.augenzahl.wert for wurf in self.wuerfe)

    def __repr__(self):
        return f"Spieler(name={self.name.name}, throws={self.anzahl_wuerfe()})"
