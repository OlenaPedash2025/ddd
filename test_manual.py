# tests.py
# Complete test suite for Wuerfelspiel
# Run with: python3 tests.py

import json
import os

from application.services import WuerfelspieleService
from domain.aggregates import Wuerfelspiel
from domain.entities import Wurf
from domain.repositories import AbstractRepository
from domain.value_objects import Augenzahl
from infrastructure.repositories import (
    InMemoryWurfRepository,
    JsonWurfRepository,
    YamlWurfRepository,
)

# =============================================================================
# HELPER
# =============================================================================


def make_service(random_fn=None) -> WuerfelspieleService:
    """Creates a fresh in-memory service for each test."""
    spiel = Wuerfelspiel(random_fn=random_fn)
    repo = InMemoryWurfRepository()
    return WuerfelspieleService(spiel=spiel, repository=repo)


# =============================================================================
# VALUE OBJECT — Augenzahl
# =============================================================================


def test_augenzahl_valid_values():
    """All values 1-6 must be created without error."""
    for i in range(1, 7):
        a = Augenzahl(i)
        assert a.wert == i
    print("  ✅ Augenzahl: all values 1-6 are valid")


def test_augenzahl_rejects_zero():
    """0 is not a valid dice face."""
    try:
        Augenzahl(0)
        assert False, "Should have raised ValueError"
    except ValueError:
        print("  ✅ Augenzahl: rejects 0")


def test_augenzahl_rejects_seven():
    """7 is not a valid dice face."""
    try:
        Augenzahl(7)
        assert False, "Should have raised ValueError"
    except ValueError:
        print("  ✅ Augenzahl: rejects 7")


def test_augenzahl_rejects_string():
    """String is not a valid dice face."""
    try:
        Augenzahl("four")  # type: ignore
        assert False, "Should have raised TypeError"
    except TypeError:
        print("  ✅ Augenzahl: rejects string input")


def test_augenzahl_equality_by_value():
    """Two Augenzahl with same value must be equal (Value Object rule)."""
    a1 = Augenzahl(4)
    a2 = Augenzahl(4)
    assert a1 == a2, "Value Objects with same value must be equal"
    print("  ✅ Augenzahl: equality by value works")


def test_augenzahl_is_immutable():
    """Augenzahl must be immutable after creation."""
    a = Augenzahl(3)
    try:
        a.wert = 5  # type: ignore
        assert False, "Should have raised FrozenInstanceError"
    except Exception:
        print("  ✅ Augenzahl: is immutable (frozen)")


# =============================================================================
# ENTITY — Wurf
# =============================================================================


def test_wurf_has_unique_id():
    """Two Wurf entities with same Augenzahl must have different IDs."""
    w1 = Wurf(augenzahl=Augenzahl(3))
    w2 = Wurf(augenzahl=Augenzahl(3))
    assert w1.id != w2.id, "Each Wurf must have a unique ID"
    print("  ✅ Wurf: each throw has a unique ID")


def test_wurf_entities_not_equal():
    """Two throws with same value are NOT the same throw (Entity rule)."""
    w1 = Wurf(augenzahl=Augenzahl(4))
    w2 = Wurf(augenzahl=Augenzahl(4))
    assert w1 != w2, "Two different throws must not be equal even with same value"
    print("  ✅ Wurf: two throws with same value are not equal")


# =============================================================================
# AGGREGATE ROOT — Wuerfelspiel
# =============================================================================


def test_aggregate_always_returns_valid_range():
    """Every throw must return a value between 1 and 6."""
    spiel = Wuerfelspiel()
    for _ in range(1000):
        wurf = spiel.wuerfeln()
        assert 1 <= wurf.augenzahl.wert <= 6
    print("  ✅ Wuerfelspiel: 1000 throws — all results in [1, 6]")


def test_aggregate_emits_one_event_per_throw():
    """One call to wuerfeln() must produce exactly one event."""
    spiel = Wuerfelspiel(random_fn=lambda: 6)
    spiel.wuerfeln()
    events = spiel.pop_events()
    assert len(events) == 1, f"Expected 1 event, got {len(events)}"
    assert events[0].wurf.augenzahl.wert == 6
    print("  ✅ Wuerfelspiel: emits exactly one event per throw")


def test_aggregate_pop_events_clears_queue():
    """After pop_events(), the event list must be empty."""
    spiel = Wuerfelspiel(random_fn=lambda: 2)
    spiel.wuerfeln()
    spiel.pop_events()  # first pop — returns 1 event
    events = spiel.pop_events()  # second pop — must be empty
    assert len(events) == 0, "Events must be cleared after pop"
    print("  ✅ Wuerfelspiel: pop_events() clears the queue")


def test_aggregate_dependency_injection():
    """Injected random_fn must control the dice result (testability)."""
    spiel = Wuerfelspiel(random_fn=lambda: 4)
    for _ in range(10):
        wurf = spiel.wuerfeln()
        assert wurf.augenzahl.wert == 4, "Deterministic fn must always return 4"
    print("  ✅ Wuerfelspiel: dependency injection works (always returns 4)")


# =============================================================================
# REPOSITORY — InMemoryWurfRepository
# =============================================================================


def test_inmemory_repository_starts_empty():
    """Fresh repository must have 0 throws."""
    repo = InMemoryWurfRepository()
    assert repo.anzahl() == 0
    assert repo.alle() == []
    print("  ✅ InMemoryRepository: starts empty")


def test_inmemory_repository_speichern():
    """Saved throw must be retrievable."""
    repo = InMemoryWurfRepository()
    wurf = Wurf(augenzahl=Augenzahl(5))
    repo.speichern(wurf)
    assert repo.anzahl() == 1
    assert repo.alle()[0].augenzahl.wert == 5
    print("  ✅ InMemoryRepository: saves and retrieves correctly")


def test_inmemory_is_not_persistent():
    """InMemoryRepository must report itself as not persistent."""
    repo = InMemoryWurfRepository()
    assert repo.ist_persistent() is False
    print("  ✅ InMemoryRepository: correctly reports not persistent")


def test_abstract_repository_cannot_be_instantiated():
    """AbstractRepository must not be instantiable directly."""
    try:
        AbstractRepository()  # type: ignore
        assert False, "Should have raised TypeError"
    except TypeError:
        print("  ✅ AbstractRepository: cannot be instantiated directly")


# =============================================================================
# REPOSITORY — JsonWurfRepository
# =============================================================================


def test_json_repository_creates_file():
    """JSON file must be created after saving a throw."""
    test_file = "test_spielstand.json"
    if os.path.exists(test_file):
        os.remove(test_file)

    repo = JsonWurfRepository(filepath=test_file)
    wurf = Wurf(augenzahl=Augenzahl(3))
    repo.speichern(wurf)

    assert os.path.exists(test_file), "JSON file must be created"

    with open(test_file, "r") as f:
        data = json.load(f)

    assert data["total"] == 1
    assert data["throws"][0]["wert"] == 3

    os.remove(test_file)
    print("  ✅ JsonRepository: creates valid JSON file")


def test_json_repository_is_persistent():
    """JsonWurfRepository must report itself as persistent."""
    test_file = "test_persistent.json"
    repo = JsonWurfRepository(filepath=test_file)
    assert repo.ist_persistent() is True
    if os.path.exists(test_file):
        os.remove(test_file)
    print("  ✅ JsonRepository: correctly reports persistent")


# =============================================================================
# APPLICATION SERVICE — WuerfelspieleService
# =============================================================================


def test_service_wuerfeln_saves_to_repository():
    """After wuerfeln(), throw must be saved in repository."""
    service = make_service(random_fn=lambda: 4)
    service.wuerfeln()
    assert service.gesamtwuerfe() == 1
    print("  ✅ Service: throw is saved to repository after wuerfeln()")


def test_service_can_roll_unlimited_times():
    """Game must impose no limit on number of rolls."""
    service = make_service(random_fn=lambda: 3)
    for i in range(10_000):
        wurf = service.wuerfeln()
        assert wurf is not None
    assert service.gesamtwuerfe() == 10_000
    print("  ✅ Service: no limit on number of rolls (10,000 throws)")


# =============================================================================
# ACCEPTANCE CRITERIA — User Story 1 (basic dice roll)
# =============================================================================


def test_ac1_result_always_between_1_and_6():
    """AC1: result must always be an integer between 1 and 6 inclusive."""
    service = make_service()
    for _ in range(1000):
        wurf = service.wuerfeln()
        assert 1 <= wurf.augenzahl.wert <= 6
    print("  ✅ AC1: result always between 1 and 6")


# =============================================================================
# ACCEPTANCE CRITERIA — User Story 2 (statistics after each throw)
# =============================================================================


def test_ac_gesamtwuerfe_nach_drei_wuerfen():
    """AC: after 3 throws, total count must be exactly 3."""
    service = make_service()
    service.wuerfeln()
    service.wuerfeln()
    service.wuerfeln()
    assert service.gesamtwuerfe() == 3
    print("  ✅ AC: total count is exactly 3 after 3 throws")


def test_ac_statistik_nach_6_6_1():
    """AC: rolling 6,6,1 → statistik shows {6:2, 1:1, rest:0}."""
    sequence = [6, 6, 1]
    index = 0

    def next_value():
        nonlocal index
        value = sequence[index]
        index += 1
        return value

    service = make_service(random_fn=next_value)
    service.wuerfeln()  # 6
    service.wuerfeln()  # 6
    service.wuerfeln()  # 1

    stats = service.statistik()
    assert stats[6] == 2, f"Expected 6 to appear 2×, got {stats[6]}"
    assert stats[1] == 1, f"Expected 1 to appear 1×, got {stats[1]}"
    assert stats[2] == 0
    assert stats[3] == 0
    assert stats[4] == 0
    assert stats[5] == 0
    print("  ✅ AC: statistik correctly shows 6×2, 1×1, rest 0")


def test_ac_gleichverteilung():
    """AC: uniform distribution over many throws (±5% tolerance)."""
    service = make_service()
    for _ in range(6000):
        service.wuerfeln()

    stats = service.statistik()
    ideal = 6000 / 6  # 1000
    tolerance = 6000 * 0.05  # 5% = 300

    for face, count in stats.items():
        deviation = abs(count - ideal)
        assert deviation < tolerance, (
            f"Face {face}: {count}×, deviation {deviation:.0f} > {tolerance:.0f}"
        )
    print("  ✅ AC: uniform distribution over 6000 throws (±5%)")


# =============================================================================
# ACCEPTANCE CRITERIA — User Story 3 (fresh start on restart)
# =============================================================================


def test_ac_frischer_start():
    """AC: fresh start — all counters must be 0."""
    service = make_service()
    assert service.gesamtwuerfe() == 0
    stats = service.statistik()
    for face, count in stats.items():
        assert count == 0, f"Face {face} must be 0 on fresh start"
    print("  ✅ AC: fresh start — all counters are 0")


# =============================================================================
# ACCEPTANCE CRITERIA — User Story 4 (save to JSON)
# =============================================================================


def test_ac_json_datei_wird_erstellt():
    """AC: game must be saved to a valid JSON file."""
    test_file = "test_ac_spielstand.json"
    if os.path.exists(test_file):
        os.remove(test_file)

    repo = JsonWurfRepository(filepath=test_file)
    spiel = Wuerfelspiel(random_fn=lambda: 3)
    service = WuerfelspieleService(spiel=spiel, repository=repo)

    service.wuerfeln()
    service.wuerfeln()
    service.wuerfeln()

    assert os.path.exists(test_file), "JSON file must be created"

    with open(test_file, "r") as f:
        data = json.load(f)

    assert data["total"] == 3, f"Expected 3 throws, got {data['total']}"
    assert len(data["throws"]) == 3
    assert data["throws"][0]["wert"] == 3

    os.remove(test_file)
    print("  ✅ AC: JSON file created with correct data after 3 throws")


def test_ac_neues_spiel_startet_frisch():
    """AC: new session must start fresh — no data from previous session."""
    test_file = "test_ac_fresh.json"

    # session 1: throw 3 times
    repo1 = JsonWurfRepository(filepath=test_file)
    spiel1 = Wuerfelspiel(random_fn=lambda: 4)
    service1 = WuerfelspieleService(spiel=spiel1, repository=repo1)
    service1.wuerfeln()
    service1.wuerfeln()
    service1.wuerfeln()
    assert service1.gesamtwuerfe() == 3

    # session 2: must not see session 1 data
    repo2 = JsonWurfRepository(filepath=test_file)
    spiel2 = Wuerfelspiel(random_fn=lambda: 6)
    service2 = WuerfelspieleService(spiel=spiel2, repository=repo2)
    service2.wuerfeln()

    assert service2.gesamtwuerfe() == 1, (
        f"New session must start with 1 throw, got {service2.gesamtwuerfe()}"
    )

    os.remove(test_file)
    print("  ✅ AC: new session always starts fresh")


def test_ac2_format_wahl_json():
    """AC2: choosing JSON creates a .json file."""
    test_file = "test_format.json"
    if os.path.exists(test_file):
        os.remove(test_file)

    repo = JsonWurfRepository(filepath=test_file)
    spiel = Wuerfelspiel(random_fn=lambda: 3)
    service = WuerfelspieleService(spiel=spiel, repository=repo)
    service.wuerfeln()

    assert os.path.exists(test_file)
    assert test_file.endswith(".json")
    os.remove(test_file)
    print("  ✅ AC2: JSON format creates .json file")


def test_ac2_format_wahl_yaml():
    """AC2: choosing YAML creates a .yaml file."""
    test_file = "test_format.yaml"
    if os.path.exists(test_file):
        os.remove(test_file)

    repo = YamlWurfRepository(filepath=test_file)
    spiel = Wuerfelspiel(random_fn=lambda: 3)
    service = WuerfelspieleService(spiel=spiel, repository=repo)
    service.wuerfeln()

    assert os.path.exists(test_file)
    assert test_file.endswith(".yaml")
    os.remove(test_file)
    print("  ✅ AC2: YAML format creates .yaml file")


def test_ac_xml_datei_wird_erstellt():
    """AC: XML file must be created after saving throws."""
    test_file = "test_spielstand.xml"
    if os.path.exists(test_file):
        os.remove(test_file)

    from infrastructure.repositories import XmlWurfRepository

    repo = XmlWurfRepository(filepath=test_file)
    spiel = Wuerfelspiel(random_fn=lambda: 3)
    service = WuerfelspieleService(spiel=spiel, repository=repo)

    service.wuerfeln()
    service.wuerfeln()
    service.wuerfeln()

    assert os.path.exists(test_file), "XML file must be created"

    import xml.etree.ElementTree as ET

    tree = ET.parse(test_file)
    root = tree.getroot()

    assert root.tag == "spielstand"
    assert root.get("total") == "3"
    assert len(root.findall("wurf")) == 3
    assert root.findall("wurf")[0].get("wert") == "3"

    os.remove(test_file)
    print("  ✅ AC XML: XML file created with correct structure")


def test_ac_xml_laden():
    """AC: existing XML file must be loadable on restart."""
    test_file = "test_xml_laden.xml"

    from infrastructure.repositories import XmlWurfRepository

    # session 1: save 3 throws
    repo1 = XmlWurfRepository(filepath=test_file)
    spiel1 = Wuerfelspiel(random_fn=lambda: 5)
    service1 = WuerfelspieleService(spiel=spiel1, repository=repo1)
    service1.wuerfeln()
    service1.wuerfeln()
    service1.wuerfeln()
    assert service1.gesamtwuerfe() == 3

    # session 2: load existing file
    repo2 = XmlWurfRepository(filepath=test_file)
    repo2.laden()
    spiel2 = Wuerfelspiel(random_fn=lambda: 2)
    service2 = WuerfelspieleService(spiel=spiel2, repository=repo2)

    assert service2.gesamtwuerfe() == 3, (
        f"Should load 3 existing throws, got {service2.gesamtwuerfe()}"
    )

    os.remove(test_file)
    print("  ✅ AC XML: existing XML file loads correctly on restart")


def test_ac_zeitstempel_im_dateinamen():
    """AC: filename must contain date and time, no old file overwritten."""
    import time

    from infrastructure.repositories import JsonWurfRepository

    repo1 = JsonWurfRepository()
    file1 = repo1._filepath

    time.sleep(1)  # wait 1 second so timestamps differ

    repo2 = JsonWurfRepository()
    file2 = repo2._filepath

    assert file1 != file2, "Each session must create a unique filename"
    assert "save_" in file1, "Filename must start with 'save_'"
    assert file1.endswith(".json"), "JSON repo must create .json file"

    print(f"  ✅ AC Zeitstempel: unique filenames: {file1} vs {file2}")


def test_ac_spielstand_finder_findet_dateien():
    """AC: SpielstandFinder must find save files."""
    import time

    from domain.entities import Wurf
    from domain.value_objects import Augenzahl
    from infrastructure.repositories import JsonWurfRepository
    from infrastructure.spielstand_finder import SpielstandFinder

    repo1 = JsonWurfRepository()
    repo1.speichern(Wurf(augenzahl=Augenzahl(3)))
    time.sleep(1)
    repo2 = JsonWurfRepository()
    repo2.speichern(Wurf(augenzahl=Augenzahl(5)))

    finder = SpielstandFinder()
    dateien = finder.finde_alle()

    assert len(dateien) >= 2
    assert dateien[0] == repo2._filepath  # newest first

    os.remove(repo1._filepath)
    os.remove(repo2._filepath)
    print("  ✅ AC Finder: finds files sorted newest first")


# =============================================================================
# RUN ALL TESTS
# =============================================================================

if __name__ == "__main__":
    tests = [
        # Value Object
        ("Augenzahl — valid values", test_augenzahl_valid_values),
        ("Augenzahl — rejects 0", test_augenzahl_rejects_zero),
        ("Augenzahl — rejects 7", test_augenzahl_rejects_seven),
        ("Augenzahl — rejects string", test_augenzahl_rejects_string),
        ("Augenzahl — equality by value", test_augenzahl_equality_by_value),
        ("Augenzahl — immutable", test_augenzahl_is_immutable),
        # Entity
        ("Wurf — unique ID", test_wurf_has_unique_id),
        ("Wurf — entities not equal", test_wurf_entities_not_equal),
        # Aggregate
        ("Aggregate — valid range", test_aggregate_always_returns_valid_range),
        ("Aggregate — one event per throw", test_aggregate_emits_one_event_per_throw),
        ("Aggregate — pop clears queue", test_aggregate_pop_events_clears_queue),
        ("Aggregate — DI works", test_aggregate_dependency_injection),
        # Repository
        ("InMemory — starts empty", test_inmemory_repository_starts_empty),
        ("InMemory — saves correctly", test_inmemory_repository_speichern),
        ("InMemory — not persistent", test_inmemory_is_not_persistent),
        (
            "Abstract — not instantiable",
            test_abstract_repository_cannot_be_instantiated,
        ),
        ("Json — creates file", test_json_repository_creates_file),
        ("Json — is persistent", test_json_repository_is_persistent),
        # Service
        ("Service — saves after roll", test_service_wuerfeln_saves_to_repository),
        ("Service — unlimited rolls", test_service_can_roll_unlimited_times),
        # Acceptance Criteria
        ("AC1 — result 1-6", test_ac1_result_always_between_1_and_6),
        ("AC2 — count after 3 throws", test_ac_gesamtwuerfe_nach_drei_wuerfen),
        ("AC2 — statistik 6,6,1", test_ac_statistik_nach_6_6_1),
        ("AC2 — uniform distribution", test_ac_gleichverteilung),
        ("AC3 — fresh start", test_ac_frischer_start),
        ("AC4 — JSON file created", test_ac_json_datei_wird_erstellt),
        ("AC4 — new session fresh", test_ac_neues_spiel_startet_frisch),
        ("AC2 — JSON format", test_ac2_format_wahl_json),
        ("AC2 — YAML format", test_ac2_format_wahl_yaml),
        ("AC XML — file created", test_ac_xml_datei_wird_erstellt),
        ("AC XML — file loads", test_ac_xml_laden),
        ("AC Zeitstempel — unique filenames", test_ac_zeitstempel_im_dateinamen),
        ("AC Finder — finds and sorts files", test_ac_spielstand_finder_findet_dateien),
    ]

    print("\n🧪 Running all tests...\n")
    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            print(f"[{name}]")
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  💥 ERROR: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'=' * 45}")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"{'=' * 45}\n")
