# presentation/konsole.py

from application.services import WuerfelspieleService
from domain.value_objects import AnzahlSpieler, Spielername


class KonsolenUI:
    """
    Presentation Layer: text-based user interface in the terminal.

    Knows about:
    - WuerfelspieleService (calls it for all game operations)

    Does NOT know about:
    - Domain objects directly (never creates Wurf or Augenzahl)
    - Repositories (never touches storage)
    - Business rules (never validates dice values)
    """

    # dice face symbols — purely visual, lives here in presentation
    DICE_FACES = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}
    BAR_CHAR = "█"
    BAR_MAX_WIDTH = 30

    def __init__(self, service: WuerfelspieleService | None = None):
        self._service = service

    def set_service(self, service: WuerfelspieleService) -> None:
        self._service = service

    def starten(self) -> None:
        """
        Start and run the game.

        Flow:
        1. Show welcome banner
        2. Ask how many players
        3. Ask for each player's name (with validation)
        4. Register players in the service
        5. Run game loop — turn order is now owned by the Aggregate;
           the UI just asks "who is up?" and reacts.
        """
        self._zeige_willkommen()

        spieler = self._service.alle_spieler()
        if not spieler:
            # Step 1: Ask how many players
            anzahl = self.frage_anzahl_spieler()
            rundenlimit = self.frage_rundenlimit()
            self._service.set_round_limit(rundenlimit)

            # Step 2: Ask for names of all players
            namen = self.frage_spielernamen(anzahl)

            # Step 3: Register players in the service (Aggregate)
            spieler = []
            for name in namen:
                p = self._service.add_spieler(name)
                spieler.append(p)

            # Step 4: turn order starts now — Aggregate picks the first player
            self._service.starte_runde()

            print(f"\n✅ Game set! {anzahl} player(s) ready:")
            for i, p in enumerate(spieler, 1):
                print(f"   {i}. {p.name.name}")
        else:
            print(f"\n✅ Loaded saved game with {len(spieler)} player(s):")
            for i, p in enumerate(spieler, 1):
                print(f"   {i}. {p.name.name}")

            if self._service.get_round_limit() is None:
                rundenlimit = self.frage_rundenlimit()
                self._service.set_round_limit(rundenlimit)
            else:
                rundenlimit = self._service.get_round_limit()

            aktueller_runde = self._service.get_current_round()
            print(f"\n🔢 Round limit: {rundenlimit}")
            print(f"🔄 Runde {aktueller_runde} / {rundenlimit}")

            if self._service.aktueller_spieler_id() is None:
                self._service.starte_runde()

            naechster_name = self._spieler_name_by_id(
                spieler, self._service.aktueller_spieler_id()
            )
            print(f"\n👉 Next turn: {naechster_name}")

        while True:
            if self._service.ist_spiel_beendet():
                self._zeige_abschluss()
                break

            aktuelle_id = self._service.aktueller_spieler_id()
            aktueller_spieler = next(p for p in spieler if p.id == aktuelle_id)
            self._zeige_zuginfo(aktueller_spieler.name.name)

            # Ask the current player if they want to roll
            antwort = self._frage_ob_spieler_wuerfeln(aktueller_spieler.name.name)

            if not antwort:
                # Current player declines — Aggregate advances the turn
                war_letzter_im_kreis = self._ist_letzter_spieler(spieler, aktuelle_id)
                self._service.spieler_aussetzen()

                if war_letzter_im_kreis:
                    # We cycled through all players once without anyone wanting to play
                    # Ask if they want to continue or stop
                    antwort_fortfahren = self._frage_ob_weitermachen()
                    if not antwort_fortfahren:
                        self._zeige_abschluss()
                        break
                continue

            # Current player wants to roll — Aggregate advances the turn itself
            wurf = self._service.wuerfeln_fuer_spieler(aktueller_spieler.id)

            # Display result
            self._zeige_ergebnis(aktueller_spieler.name.name, wurf.augenzahl.wert)

    def _spieler_name_by_id(self, spieler: list, spieler_id: str | None) -> str:
        """Look up a player's display name by ID — small UI helper."""
        gefunden = next((p for p in spieler if p.id == spieler_id), None)
        return gefunden.name.name if gefunden else "?"

    def _ist_letzter_spieler(self, spieler: list, spieler_id: str | None) -> bool:
        """
        True if spieler_id is the last player in registration order —
        used only to decide when to ask "continue?" after a full pass
        of everyone declining. Pure UI bookkeeping, not a domain rule.
        """
        if not spieler:
            return False
        return spieler[-1].id == spieler_id

    def _zeige_willkommen(self) -> None:
        """Print welcome banner — called exactly once."""
        print("\n" + "=" * 45)
        print("       🎲  W Ü R F E L S P I E L  🎲")
        print("=" * 45)
        print("  Roll as many times as you like!")
        print("=" * 45)

    def _frage_ob_spieler_wuerfeln(self, spieler_name: str) -> bool:
        """
        Ask a specific player if they want to roll.
        Loops until valid input is given — no crashes on typos.

        Args:
            spieler_name: The name of the current player.

        Returns:
            True if player wants to roll, False if they want to skip their turn.
        """
        while True:
            try:
                eingabe = (
                    input(f"\n🎲 {spieler_name}, roll the dice? (j/n): ")
                    .strip()
                    .lower()
                )
            except (EOFError, KeyboardInterrupt):
                # handle Ctrl+C and Ctrl+D gracefully
                print("\n\nGame interrupted. Bye!")
                return False

            if eingabe in ("j", "y"):
                return True
            elif eingabe in ("n"):
                return False
            else:
                print("  ⚠️  Please enter 'j' (yes) or 'n' (no).")

    def _frage_ob_weitermachen(self) -> bool:
        """
        Ask if the game should continue (everyone declined their turn).

        Returns:
            True to continue (next round), False to end the game.
        """
        while True:
            try:
                eingabe = (
                    input("\n🎲 Everyone passed. Continue? (j/n): ").strip().lower()
                )
            except (EOFError, KeyboardInterrupt):
                print("\n\nGame interrupted. Bye!")
                return False

            if eingabe in ("j", "y"):
                return True
            elif eingabe in ("n"):
                return False
            else:
                print("  ⚠️  Please enter 'j' (yes) or 'n' (no).")

    def frage_anzahl_spieler(self) -> int:
        """
        Ask how many players will play the game.
        Loops until valid input is given (1-99).

        Returns:
            Number of players (1-99).
        """
        while True:
            try:
                eingabe = input("\n👥 How many players? (1-99): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nGame interrupted. Bye!")
                raise

            try:
                anzahl = int(eingabe)
                # Validate using the domain Value Object
                AnzahlSpieler(anzahl)
                return anzahl
            except ValueError as e:
                print(f"  ⚠️  {e}")
            except TypeError as e:
                print(f"  ⚠️  {e}")

    def frage_rundenlimit(self) -> int:
        """
        Ask for the round limit before the game starts.

        Returns:
            The round limit as an integer greater than zero.
        """
        while True:
            try:
                eingabe = input(
                    "\n⏱️  How many rounds should the game run? (1-999): "
                ).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nGame interrupted. Bye!")
                raise

            try:
                limit = int(eingabe)
                if limit < 1 or limit > 999:
                    raise ValueError("Please enter a number between 1 and 999.")
                return limit
            except ValueError as e:
                print(f"  ⚠️  {e}")

    def frage_spielernamen(self, anzahl: int) -> list[str]:
        """
        Ask for the names of all players.
        Loops per player until valid names are given (letters only, min 3 chars).

        Args:
            anzahl: Number of players to ask for.

        Returns:
            List of validated player names.
        """
        namen = []
        print(f"\n👤 Enter names for {anzahl} player(s):")

        for i in range(1, anzahl + 1):
            while True:
                try:
                    eingabe = input(f"  Player {i}: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n\nGame interrupted. Bye!")
                    raise

                try:
                    # Validate using the domain Value Object
                    spielername = Spielername(eingabe)
                    namen.append(spielername.name)
                    break
                except ValueError as e:
                    print(f"    ⚠️  {e}")
                except TypeError as e:
                    print(f"    ⚠️  {e}")

        return namen

    def _zeige_ergebnis(self, spieler_name: str, wert: int) -> None:
        """
        Display the result of a single throw for a specific player.

        Args:
            spieler_name: Name of the player who rolled.
            wert: The result of the throw (1-6).
        """
        symbol = self.DICE_FACES.get(wert, "?")
        print(f"\n  ▶ {spieler_name} rolled: {symbol}  {wert}")
        self._zeige_statistik()

    def _zeige_zuginfo(self, spieler_name: str) -> None:
        """
        Display the current round and current player before each turn.
        """
        current_round = self._service.get_current_round()
        round_limit = self._service.get_round_limit()
        limit_text = str(round_limit) if round_limit is not None else "∞"
        print(f"\n🔄 Runde {current_round} / {limit_text}")
        print(f"👉 {spieler_name} ist jetzt dran.")

    def _zeige_statistik(self) -> None:
        """
        Display a formatted statistics table after every throw.

        Acceptance Criteria:
        - total throw count is exact
        - each face shows correct frequency
        - output is human-readable, not a raw data object
        """
        gesamt = self._service.gesamtwuerfe()
        stats = self._service.statistik()

        # find the highest count to scale the bars proportionally
        # if nobody has thrown yet, avoid division by zero
        max_count = max(stats.values()) if gesamt > 0 else 1

        width = 38  # total width of the box content

        print(
            f"\n  ┌─ Statistics after {gesamt} throw(s) {'─' * (width - 22 - len(str(gesamt)))}┐"
        )

        for face in range(1, 7):
            count = stats[face]
            symbol = self.DICE_FACES[face]

            # filled part — proportional to this face's count
            filled = int((count / max_count) * 20) if max_count > 0 else 0
            empty = 20 - filled

            bar = self.BAR_CHAR * filled + "░" * empty

            print(f"  │  {symbol} {face}:  {bar}  {count:>3}×  │")

        print(f"  └{'─' * (width + 3)}┘")

    def _zeige_abschluss(self) -> None:
        """
        Display final statistics.
        Acceptance Criterion 2: verify uniform distribution.
        """
        gesamt = self._service.gesamtwuerfe()

        if gesamt == 0:
            print("\n  No throws made. Come back soon! 👋")
            return

        stats = self._service.statistik()
        max_count = max(stats.values())

        if self._service.ist_persistent():
            print("\n  💾 Your game has been saved to spielstand.json")

        print("\n" + "=" * 45)
        print(f"  📊  STATISTICS after {gesamt} throw(s)")
        print("=" * 45)

        for face in range(1, 7):
            count = stats[face]
            symbol = self.DICE_FACES[face]
            # scale bar width relative to the most frequent face
            bar_width = int((count / max_count) * self.BAR_MAX_WIDTH)
            bar = self.BAR_CHAR * bar_width
            percentage = count / gesamt * 100
            print(
                f"  {symbol} {face}: {bar:<{self.BAR_MAX_WIDTH}} {count:>4}×  ({percentage:4.1f}%)"
            )

        ideal = gesamt / 6
        print("-" * 45)
        print(f"  Ideal (uniform): each face ≈ {ideal:.1f}×")
        print("=" * 45)
        print("  Thanks for playing! 🎉")

    def frage_nach_format(self) -> str:
        print("\n  💾 Choose save format:")
        print("     j → JSON  (spielstand.json)")
        print("     y → YAML  (spielstand.yaml)")
        print("     x → XML   (spielstand.xml)")  # ← новый вариант

        while True:
            try:
                eingabe = input("\n  Your choice (j/y/x): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return "json"

            if eingabe == "j":
                return "json"
            elif eingabe == "y":
                return "yaml"
            elif eingabe == "x":  # ← новый вариант
                return "xml"
            else:
                print("  ⚠️  Please enter 'j', 'y' or 'x'.")

    def frage_nach_spielstand(self, vorhandene_dateien: list[str]) -> str | None:
        """
        Show existing save files and ask player what to do.

        Args:
            vorhandene_dateien: list of save files found on disk.

        Returns:
            filename to load, or None if player wants a new game.
        """
        print("\n  📁 Existing save files:")
        print("     0 → New game")

        for i, dateiname in enumerate(vorhandene_dateien, start=1):
            print(f"     {i} → {dateiname}")

        while True:
            try:
                eingabe = input(
                    f"\n  Your choice (0-{len(vorhandene_dateien)}): "
                ).strip()
            except (EOFError, KeyboardInterrupt):
                return None

            if eingabe == "0":
                return None  # new game

            if eingabe.isdigit():
                index = int(eingabe) - 1
                if 0 <= index < len(vorhandene_dateien):
                    return vorhandene_dateien[index]  # return chosen filename

            print(
                f"  ⚠️  Please enter a number between 0 and {len(vorhandene_dateien)}."
            )

    def frage_ob_fortsetzen(
        self,
        spieler_namen: list[str],
        aktueller_runde: int,
        rundenlimit: int | None,
        naechster_spieler: str,
    ) -> bool:
        """
        Ask the player whether to resume a loaded game or start fresh.
        """
        print("\n✅ Found a saved game ready to continue:")
        print(f"  Players: {', '.join(spieler_namen)}")
        limit_text = str(rundenlimit) if rundenlimit is not None else "unlimited"
        print(f"  Round limit: {limit_text}")
        print(f"  Current round: {aktueller_runde} / {limit_text}")
        print(f"  Next player: {naechster_spieler}")

        while True:
            try:
                eingabe = input("\n  Resume this saved game? (j/n): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n\nGame interrupted. Bye!")
                return False

            if eingabe in ("j", "y"):
                return True
            if eingabe in ("n", "no"):
                return False
            print("  ⚠️  Please enter 'j' (yes) or 'n' (no).")
