# main.py — Composition Root
# The ONLY place where all layers are imported and wired together.

from application.services import WuerfelspieleService
from domain.aggregates import Wuerfelspiel
from infrastructure.repositories import (
    JsonWurfRepository,
    XmlWurfRepository,
    YamlWurfRepository,
)
from infrastructure.spielstand_finder import SpielstandFinder
from presentation.konsole import KonsolenUI


def main() -> None:
    """
    Build the dependency tree and start the application.

    Assembly order:
    1. Create UI (no service yet)
    2. Look for existing save files
    3. Ask player what to do (load existing or start new)
    4. Create the right repository based on choice
    5. Wire everything together and start
    """

    # step 1: create UI first — no service yet
    ui = KonsolenUI()

    # step 2: look for existing save files on disk
    finder = SpielstandFinder()
    vorhandene_dateien = finder.finde_alle()

    if vorhandene_dateien:
        # step 3a: files exist — ask player to choose
        wahl = ui.frage_nach_spielstand(vorhandene_dateien)

        if wahl is not None:
            # player chose an existing file — create repo and load data
            if wahl.endswith(".json"):
                repository = JsonWurfRepository(filepath=wahl)
            elif wahl.endswith(".yaml"):
                repository = YamlWurfRepository(filepath=wahl)
            else:
                repository = XmlWurfRepository(filepath=wahl)

            # load existing throws from file into repository
            repository.laden()

        else:
            # player chose new game — ask format
            format_wahl = ui.frage_nach_format()
            if format_wahl == "json":
                repository = JsonWurfRepository()
            elif format_wahl == "yaml":
                repository = YamlWurfRepository()
            else:
                repository = XmlWurfRepository()

    else:
        # step 3b: no files exist — straight to new game
        format_wahl = ui.frage_nach_format()
        if format_wahl == "json":
            repository = JsonWurfRepository()
        elif format_wahl == "yaml":
            repository = YamlWurfRepository()
        else:
            repository = XmlWurfRepository()

    # step 4: wire everything together (runs regardless of which path above)
    spiel = Wuerfelspiel()
    service = WuerfelspieleService(spiel=spiel, repository=repository)
    ui.set_service(service)

    if repository.ist_persistent():
        meta = repository.get_meta()
        if meta.get("players"):
            service.restore_state(meta)
            spieler = service.alle_spieler()
            if spieler:
                current_player_id = service.aktueller_spieler_id() or spieler[0].id
                next_player_name = next(
                    (p.name.name for p in spieler if p.id == current_player_id),
                    spieler[0].name.name,
                )
                if not ui.frage_ob_fortsetzen(
                    [p.name.name for p in spieler],
                    service.get_current_round(),
                    service.get_round_limit(),
                    next_player_name,
                ):
                    format_wahl = ui.frage_nach_format()
                    if format_wahl == "json":
                        repository = JsonWurfRepository()
                    elif format_wahl == "yaml":
                        repository = YamlWurfRepository()
                    else:
                        repository = XmlWurfRepository()

                    spiel = Wuerfelspiel()
                    service = WuerfelspieleService(spiel=spiel, repository=repository)
                    ui.set_service(service)

    ui.starten()


if __name__ == "__main__":
    main()
