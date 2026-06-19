from dataclasses import dataclass

from domain.entities import Wurf


@dataclass(frozen=True)
class WurfAusgeloest:
    """
    Domain Event: "a throw was triggered by a specific player."

    Named in past tense — this fact has already happened.
    Collected by the Aggregate, dispatched by the Application Service.

    Carries:
    - The full Wurf entity with the result
    - The spieler_id so we know WHO threw it

    This allows tracking which player made which throw.
    """

    wurf: Wurf
    spieler_id: str  # New: track WHO made this throw
