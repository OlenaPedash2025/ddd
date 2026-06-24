# application/services.py

from domain.aggregates import Wuerfelspiel
from domain.entities import Spieler, Wurf
from domain.repositories import AbstractRepository
from domain.value_objects import Spielername


class WuerfelspieleService:
    """
    Application Service: orchestrates the game flow.

    ARCHITECTURE (after turn-order refactor):
    - Turn order, round limit, and current round are NOT stored here anymore.
      They live on the Aggregate (Wuerfelspiel) — it is the single source
      of truth and the only place that enforces "whose turn is it".
    - This Service is a thin coordinator: it calls the Aggregate, then
      reacts to what happened (persists throws, syncs metadata).

    Knows about:
    - Domain Aggregate (Wuerfelspiel) — owns all game state
    - Domain Entities (Spieler) — read-only access
    - Repository Interface (AbstractRepository)

    Does NOT know about:
    - Concrete repository implementations
    - UI details (no print statements here)
    - Business rules (never validates — that's Aggregate's job)
    """

    def __init__(
        self,
        spiel: Wuerfelspiel,
        repository: AbstractRepository,  # accepts ANY implementation
    ):
        self._spiel = spiel
        self._repository = repository

    def _sync_meta(self) -> None:
        """
        Push the Aggregate's current state into the repository's metadata.
        Called after any operation that changes players, turn order, or
        round state — keeps the save file always up to date.
        """
        if not self._repository.ist_persistent():
            return

        self._repository.set_meta(
            {
                "players": [
                    {"id": spieler.id, "name": spieler.name.name}
                    for spieler in self._spiel.alle_spieler()
                ],
                "next_player_id": self._spiel.aktueller_spieler_id(),
                "round_limit": self._spiel.get_round_limit(),
                "current_round": self._spiel.aktuelle_runde(),
            }
        )

    def add_spieler(self, name: str) -> Spieler:
        """
        Register a new player.

        ARCHITECTURE: Service accepts raw string from UI,
        Aggregate creates the domain entity with validation.

        Args:
            name: Player's name (will be validated by Spielername value object)

        Returns:
            The newly created Spieler entity.

        Raises:
            ValueError: If name validation fails (delegates to domain)
        """
        spielername = Spielername(name)  # Validate in domain layer
        spieler = self._spiel.add_spieler(spielername)
        self._sync_meta()
        return spieler

    def alle_spieler(self) -> list[Spieler]:
        """
        Return all players in the current game.

        Returns:
            List of all Spieler entities.
        """
        return self._spiel.alle_spieler()

    def starte_runde(self) -> None:
        """
        Start the turn order — the first registered player becomes current.
        Must be called once after all players are registered (Variant A:
        explicit start, see Wuerfelspiel.starte_runde docstring).
        """
        self._spiel.starte_runde()
        self._sync_meta()

    def aktueller_spieler_id(self) -> str | None:
        """Return the ID of the player whose turn it currently is."""
        return self._spiel.aktueller_spieler_id()

    def set_round_limit(self, round_limit: int | None) -> None:
        """Configure how many rounds the game runs (delegates to Aggregate)."""
        self._spiel.set_round_limit(round_limit)
        self._sync_meta()

    def get_round_limit(self) -> int | None:
        """Return the configured round limit, or None when unlimited."""
        return self._spiel.get_round_limit()

    def get_current_round(self) -> int:
        """Return the current round (delegates to Aggregate)."""
        return self._spiel.aktuelle_runde()

    def ist_spiel_beendet(self) -> bool:
        """True if the configured round limit has been reached."""
        return self._spiel.ist_spiel_beendet()

    def spieler_aussetzen(self) -> None:
        """
        Current player skips their turn. Turn order still advances —
        delegates to the Aggregate, which owns this invariant.
        """
        self._spiel.spieler_aussetzen()
        self._sync_meta()

    def restore_state(self, meta: dict) -> None:
        """
        Restore game state from loaded repository metadata.

        Args:
            meta: metadata dictionary with players, next_player_id,
                  round_limit, and current_round.
        """
        players = meta.get("players", []) or []
        throws = self._repository.alle()
        if players:
            self._spiel.load_state(
                players,
                throws,
                next_player_id=meta.get("next_player_id"),
                round_limit=meta.get("round_limit"),
                current_round=meta.get("current_round")
                or (self._repository.anzahl() // len(players) + 1),
            )

    def wuerfeln_fuer_spieler(self, spieler_id: str) -> Wurf:
        """
        Execute the "roll the dice" use case for a specific player.

        ARCHITECTURE:
        1. Aggregate performs the throw AND advances turn order (domain logic)
        2. Collect Domain Events from the Aggregate
        3. React to each event — save the throw to repository
        4. Sync metadata (next player / round may have changed)
        5. Return the result to the Presentation Layer

        Args:
            spieler_id: Which player is throwing.

        Returns:
            The newly created Wurf entity.

        Raises:
            ValueError: If spieler_id doesn't exist, or it isn't their turn.
        """
        # step 1: domain does all the work, including advancing the turn
        wurf = self._spiel.wuerfeln_fuer_spieler(spieler_id)

        # step 2: collect events — aggregate's mailbox is cleared after this
        events = self._spiel.pop_events()

        # step 3: react to events — here we persist the throw
        for event in events:
            self._repository.speichern(event.wurf)

        # step 4: turn/round may have changed — keep save file in sync
        self._sync_meta()

        # step 5: return to caller
        return wurf

    def wuerfeln(self) -> Wurf:
        """
        Convenience method for single-player / legacy usage: roll for
        whichever player is currently up. Requires starte_runde() to have
        been called and exactly the current player to roll.

        Raises:
            ValueError: If no turn order has been started yet.
        """
        spieler_id = self._spiel.aktueller_spieler_id()
        if spieler_id is None:
            raise ValueError(
                "Es ist kein Spieler am Zug. Bitte zuerst starte_runde() aufrufen."
            )
        return self.wuerfeln_fuer_spieler(spieler_id)

    def statistik(self) -> dict[int, int]:
        """
        Compute throw frequency for each face value (1-6).

        ARCHITECTURE: Works on aggregate level (all players combined).
        Used to verify uniform distribution across the game.

        Returns:
            {1: 17, 2: 18, 3: 16, 4: 19, 5: 17, 6: 16} for example
        """
        # start with zero for every face — ensures all keys always exist
        haeufigkeit: dict[int, int] = {i: 0 for i in range(1, 7)}

        for wurf in self._repository.alle():
            haeufigkeit[wurf.augenzahl.wert] += 1

        return haeufigkeit

    def statistik_fuer_spieler(self, spieler_id: str) -> dict[int, int]:
        """
        Compute throw frequency for a specific player.

        Returns:
            {1: 5, 2: 3, 3: 4, ...} for example
        """
        spieler = self._spiel.get_spieler(spieler_id)
        if spieler is None:
            raise ValueError(f"Spieler mit ID {spieler_id} nicht gefunden.")

        return spieler.statistik()

    def punkte_fuer_spieler(self, spieler_id: str) -> int:
        """
        Compute total points for a specific player.

        Returns:
            Total points (sum of all throw values) for the player.
        """
        spieler = self._spiel.get_spieler(spieler_id)
        if spieler is None:
            raise ValueError(f"Spieler mit ID {spieler_id} nicht gefunden.")

        return spieler.punkte()

    def gesamtwuerfe(self) -> int:
        """Return total number of throws in this session."""
        return self._repository.anzahl()

    def ist_persistent(self) -> bool:
        """Return True if the underlying repository persists data between sessions."""
        return self._repository.ist_persistent()
