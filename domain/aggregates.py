import random
from typing import Callable, List

from domain.entities import Spieler, Wurf
from domain.events import WurfAusgeloest
from domain.value_objects import Augenzahl, Spielername


class Wuerfelspiel:
    """
    Aggregate Root: the single entry point for all dice game operations.

    ARCHITECTURE PRINCIPLE: All state changes go through this class.
    - Only place where Spieler entities are created/managed
    - Only place where throws are recorded
    - Only place where events are generated
    - Spieler entities are PASSIVE (read-only from outside)

    Responsibilities:
    - Manage the list of players (Spieler)
    - Create Wurf entities (throws) for players
    - Enforce uniform distribution via injected random function
    - Collect Domain Events for the Application Layer to dispatch

    What it does NOT do:
    - Does NOT save to any storage (no repository calls)
    - Does NOT know about the UI
    - Does NOT dispatch events itself
    """

    def __init__(self, random_fn: Callable[[], int] | None = None):
        """
        Args:
            random_fn: function that returns an integer between 1 and 6.
                       Default: random.randint(1, 6)
                       In tests: lambda: 4  (always returns 4, no randomness)

        WHY Callable[[], int]?
            Callable       = this is a function
            [[], int]      = takes no arguments, returns int
            | None         = or None (then we use the default)
        """
        if random_fn is None:
            self.random_fn = lambda: random.randint(1, 6)
        else:
            self.random_fn = random_fn

        # NEW: Store players, not throws (throw collection is distributed across players)
        self._spieler: List[Spieler] = []

        # Events that happened but not dispatched yet
        self._pending_events: List[WurfAusgeloest] = []

        # NEW: Turn-order invariants — now owned by the Aggregate, not the UI.
        # Whose turn is it right now? None means "round not started yet".
        self._current_player_id: str | None = None

        # How many rounds does this game run? None means unlimited.
        self._round_limit: int | None = None

        # Which round are we currently in (1-based)?
        self._current_round: int = 1

    def add_spieler(self, name: Spielername) -> Spieler:
        """
        Register a new player in this game.

        Args:
            name: The player's name (validated by Spielername value object)

        Returns:
            The newly created Spieler entity.

        ARCHITECTURE: This is how Spieler entities enter the system.
        Once created, they're only modified through wuerfeln_fuer_spieler().
        """
        spieler = Spieler(name=name)
        self._spieler.append(spieler)
        return spieler

    def get_spieler(self, spieler_id: str) -> Spieler | None:
        """
        Find a player by their ID.

        Args:
            spieler_id: The unique ID of the player.

        Returns:
            The Spieler if found, None otherwise.
        """
        for spieler in self._spieler:
            if spieler.id == spieler_id:
                return spieler
        return None

    def alle_spieler(self) -> List[Spieler]:
        """
        Return all players in this game.

        Returns:
            List of all Spieler entities.
        """
        return list(self._spieler)

    def starte_runde(self) -> None:
        """
        Explicitly start the turn order: the first registered player becomes
        the current player.

        ARCHITECTURE (Variant A — explicit over implicit):
        add_spieler() does NOT silently set the current player as a side
        effect. The caller (Application Service / UI) must call this once,
        after all players have been registered, to say "the game begins now".

        Raises:
            ValueError: If no players have been registered yet.
        """
        if not self._spieler:
            raise ValueError(
                "Kann keine Runde starten — es sind keine Spieler registriert."
            )
        self._current_player_id = self._spieler[0].id

    def aktueller_spieler_id(self) -> str | None:
        """Return the ID of the player whose turn it currently is, or None."""
        return self._current_player_id

    def set_round_limit(self, round_limit: int | None) -> None:
        """
        Configure how many rounds this game runs. None means unlimited.
        This is configuration, not an invariant the Aggregate must defend —
        any value is accepted as-is.
        """
        self._round_limit = round_limit

    def get_round_limit(self) -> int | None:
        """Return the configured round limit, or None when unlimited."""
        return self._round_limit

    def aktuelle_runde(self) -> int:
        """Return the current round number (1-based)."""
        return self._current_round

    def ist_spiel_beendet(self) -> bool:
        """
        True if the configured round limit has been reached.
        Always False for unlimited games (round_limit is None).
        """
        return self._round_limit is not None and self._current_round > self._round_limit

    def wuerfeln_fuer_spieler(self, spieler_id: str) -> Wurf:
        """
        Perform a dice throw for a specific player.

        ARCHITECTURE: This is the ONLY place where throws are recorded.
        The Aggregate controls:
        1. Random generation
        2. Throw creation (Wurf entity)
        3. Player state update (adding throw to player.wuerfe)
        4. Event generation

        Args:
            spieler_id: Which player is throwing.

        Returns:
            The newly created Wurf entity.

        Raises:
            ValueError: If spieler_id doesn't exist, or if it isn't this
                        player's turn right now.
        """
        spieler = self.get_spieler(spieler_id)
        if spieler is None:
            raise ValueError(f"Spieler mit ID {spieler_id} nicht gefunden.")

        # NEW invariant: only the current player may throw.
        # None means "turn order not started" — e.g. legacy/no-rounds usage.
        if (
            self._current_player_id is not None
            and spieler_id != self._current_player_id
        ):
            raise ValueError(
                f"Spieler {spieler_id} ist nicht am Zug. "
                f"Aktuell ist Spieler {self._current_player_id} dran."
            )

        # Step 1: Generate random number
        augenzahl = Augenzahl(self.random_fn())

        # Step 2: Create Wurf entity
        wurf = Wurf(augenzahl=augenzahl, spieler_id=spieler_id)

        # Step 3: Add to player's throws (ONLY way to modify Spieler.wuerfe)
        spieler.wuerfe.append(wurf)

        # Step 4: Record domain event (with player info)
        event = WurfAusgeloest(wurf=wurf, spieler_id=spieler_id)
        self._pending_events.append(event)

        # Step 5: Advance the turn — the Aggregate owns this decision now,
        # not the UI. Only advances if turn order has actually started.
        if self._current_player_id is not None:
            self._naechster_spieler()

        return wurf

    def _naechster_spieler(self) -> None:
        """
        Advance turn order to the next player in registration order.
        When wrapping back to the first player, the round counter increases.

        Private — this is an internal invariant, never called from outside.
        """
        index = next(
            i for i, s in enumerate(self._spieler) if s.id == self._current_player_id
        )
        naechster_index = (index + 1) % len(self._spieler)
        self._current_player_id = self._spieler[naechster_index].id
        if naechster_index == 0:
            self._current_round += 1

    def spieler_aussetzen(self) -> None:
        """
        Current player explicitly skips their turn (declines to roll).
        Turn order still advances — this is a legitimate game action,
        not an error, so it goes through the Aggregate like any other move.

        Raises:
            ValueError: If turn order hasn't been started yet.
        """
        if self._current_player_id is None:
            raise ValueError("Die Runde wurde noch nicht gestartet.")
        self._naechster_spieler()

    def pop_events(self) -> List[WurfAusgeloest]:
        """
        Drain and return all pending domain events.

        Called by the Application Service after every command.
        After this call, the internal event list is empty.
        Each event is delivered exactly once — like taking letters from a mailbox.

        Returns:
            List of events since the last pop_events() call.
        """
        # copy the list before clearing
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    def alle_wuerfe(self) -> List[Wurf]:
        """
        Return a list of all throws that have happened in this game.

        Aggregates throws from all players.

        Returns:
            Flat list of all Wurf entities created in this game.
        """
        all_throws = []
        for spieler in self._spieler:
            all_throws.extend(spieler.wuerfe)
        return all_throws

    def gesamtwuerfe(self) -> int:
        """
        Return the total number of throws across all players.

        Returns:
            Total throw count.
        """
        return len(self.alle_wuerfe())

    def load_state(
        self,
        players: list[dict],
        throws: list[Wurf],
        next_player_id: str | None = None,
        round_limit: int | None = None,
        current_round: int = 1,
    ) -> None:
        """
        Restore the aggregate state from persisted metadata and throws.

        Args:
            players: list of player metadata dicts containing id and name.
            throws: list of deserialized Wurf entities.
            next_player_id: whose turn it was when the game was saved.
            round_limit: the configured round limit, if any.
            current_round: which round was in progress.
        """
        self._spieler = []

        for player_data in players:
            self._spieler.append(
                Spieler(
                    name=Spielername(player_data["name"]),
                    id=player_data["id"],
                )
            )

        for wurf in throws:
            if wurf.spieler_id is None:
                continue
            spieler = self.get_spieler(wurf.spieler_id)
            if spieler is not None:
                spieler.wuerfe.append(wurf)

        # Restore turn-order invariants — these now live on the Aggregate.
        self._current_player_id = next_player_id
        self._round_limit = round_limit
        self._current_round = current_round or 1
