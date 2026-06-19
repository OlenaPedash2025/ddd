import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime

import yaml

from domain.entities import Wurf
from domain.repositories import AbstractFileWurfRepository, AbstractRepository
from domain.value_objects import Augenzahl


class XmlWurfRepository(AbstractFileWurfRepository):
    """
    Concrete repository — persists throws to an XML file on disk.
    Data survives program restarts — unlike InMemoryWurfRepository.

    File format:
    <spielstand total="3">
        <wurf id="..." wert="4" zeitstempel="2024-01-15T14:32:01" />
        ...
    </spielstand>
    """

    def __init__(self, filepath: str | None = None):
        """
        Args:
            filepath: path to the XML file.
                      Default: spielstand.xml in the current directory.
        """

        super().__init__()

        if filepath is None:
            from datetime import datetime

            zeitstempel = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._filepath = f"save_{zeitstempel}.xml"
        else:
            self._filepath = filepath

        # load existing data if file already exists
        self._store: list[Wurf] = []

    def ist_persistent(self) -> bool:
        return True

    def _save(self) -> None:
        """
        Serialize all throws and metadata to XML and write to disk.
        Called after every speichern() or set_meta() — keeps file always up to date.
        """
        root = ET.Element(
            "spielstand",
            total=str(len(self._store)),
            next_player_id=self._meta.get("next_player_id") or "",
            round_limit=str(self._meta.get("round_limit") or ""),
            current_round=str(self._meta.get("current_round") or 1),
        )

        players_elem = ET.SubElement(root, "players")
        for player in self._meta.get("players", []):
            ET.SubElement(
                players_elem,
                "player",
                id=player["id"],
                name=player["name"],
            )

        for wurf in self._store:
            attrs = {
                "id": wurf.id,
                "wert": str(wurf.augenzahl.wert),
                "zeitstempel": wurf.zeitstempel.isoformat(),
            }
            if wurf.spieler_id is not None:
                attrs["spieler_id"] = wurf.spieler_id
            ET.SubElement(root, "wurf", **attrs)

        tree = ET.ElementTree(root)
        tree.write(self._filepath, encoding="utf-8", xml_declaration=True)

    def _load(self) -> tuple[list[Wurf], dict]:
        """
        Read XML file from disk and deserialize back to Wurf entities and metadata.
        Returns empty list and default metadata if file does not exist yet.
        """
        if not os.path.exists(self._filepath):
            return [], {"players": [], "next_player_id": None}

        tree = ET.parse(self._filepath)
        root = tree.getroot()

        players = []
        players_elem = root.find("players")
        if players_elem is not None:
            for player_elem in players_elem.findall("player"):
                players.append(
                    {
                        "id": player_elem.get("id"),
                        "name": player_elem.get("name"),
                    }
                )

        next_player_id = root.get("next_player_id") or None
        round_limit_attr = root.get("round_limit") or None
        current_round_attr = root.get("current_round") or None
        round_limit = int(round_limit_attr) if round_limit_attr else None
        current_round = int(current_round_attr) if current_round_attr else 1

        result = []
        for elem in root.findall("wurf"):
            wurf = Wurf(
                augenzahl=Augenzahl(int(elem.get("wert"))),
                zeitstempel=datetime.fromisoformat(elem.get("zeitstempel")),
                id=elem.get("id"),
                spieler_id=elem.get("spieler_id"),
            )
            result.append(wurf)

        return result, {
            "players": players,
            "next_player_id": next_player_id,
            "round_limit": round_limit,
            "current_round": current_round,
        }


class YamlWurfRepository(AbstractFileWurfRepository):
    """
    Concrete repository — persists throws to a YAML file on disk.
    Data survives program restarts — unlike InMemoryWurfRepository.

    File format:
    total: 3
    throws:
      - id: "..."
        wert: 4
        zeitstempel: "2024-01-15T14:32:01"
      ...
    """

    def __init__(self, filepath: str | None = None):
        super().__init__()

        if filepath is None:
            from datetime import datetime

            zeitstempel = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._filepath = f"save_{zeitstempel}.yaml"
        else:
            self._filepath = filepath
            # load existing data if file already exists
        self._store: list[Wurf] = []

    def ist_persistent(self) -> bool:
        return True

    def _save(self) -> None:
        """
        Serialize all throws and metadata to YAML and write to disk.
        Called after every speichern() or set_meta() — keeps file always up to date.
        """
        data = {
            "players": self._meta.get("players", []),
            "next_player_id": self._meta.get("next_player_id"),
            "round_limit": self._meta.get("round_limit"),
            "current_round": self._meta.get("current_round"),
            "total": len(self._store),
            "throws": [
                {
                    "id": wurf.id,
                    "spieler_id": wurf.spieler_id,
                    "wert": wurf.augenzahl.wert,
                    "zeitstempel": wurf.zeitstempel.isoformat(),
                }
                for wurf in self._store  # list comprehension — one dict per Wurf
            ],
        }
        with open(self._filepath, "w", encoding="utf-8") as f:
            yaml.dump(data, f, indent=2, allow_unicode=True, default_flow_style=False)

    def _load(self) -> tuple[list[Wurf], dict]:
        """
        Read YAML file from disk and deserialize back to Wurf entities and metadata.
        Returns empty list and default metadata if file does not exist yet.
        """
        if not os.path.exists(self._filepath):
            return [], {"players": [], "next_player_id": None}

        with open(self._filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        players = data.get("players", []) or []
        next_player_id = data.get("next_player_id")
        round_limit = data.get("round_limit")
        current_round = data.get("current_round", 1) or 1

        result = []
        for item in data.get("throws", []):
            wurf = Wurf(
                augenzahl=Augenzahl(item["wert"]),
                zeitstempel=datetime.fromisoformat(item["zeitstempel"]),
                id=item["id"],
                spieler_id=item.get("spieler_id"),
            )
            result.append(wurf)
        return result, {
            "players": players,
            "next_player_id": next_player_id,
            "round_limit": round_limit,
            "current_round": current_round,
        }


class JsonWurfRepository(AbstractFileWurfRepository):
    """
    Concrete repository — persists throws to a JSON file on disk.
    Data survives program restarts — unlike InMemoryWurfRepository.

    File format:
    {
        "total": 3,
        "throws": [
            {"id": "...", "wert": 4, "zeitstempel": "2024-01-15T14:32:01"},
            ...
        ]
    }
    """

    def __init__(self, filepath: str | None = None):
        """
        Args:
            filepath: path to the JSON file.
                      Default: spielstand.json in the current directory.
        """

        super().__init__()

        if filepath is None:
            from datetime import datetime

            zeitstempel = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._filepath = f"save_{zeitstempel}.json"  # ← для JSON
        else:
            self._filepath = filepath

        # load existing data if file already exists
        self._store: list[Wurf] = []

    def _save(self) -> None:
        """
        Serialize all throws and metadata to JSON and write to disk.
        Called after every speichern() or set_meta() — keeps file always up to date.
        """
        data = {
            "players": self._meta.get("players", []),
            "next_player_id": self._meta.get("next_player_id"),
            "round_limit": self._meta.get("round_limit"),
            "current_round": self._meta.get("current_round"),
            "total": len(self._store),
            "throws": [
                {
                    "id": wurf.id,
                    "spieler_id": wurf.spieler_id,
                    "wert": wurf.augenzahl.wert,
                    "zeitstempel": wurf.zeitstempel.isoformat(),
                }
                for wurf in self._store  # list comprehension — one dict per Wurf
            ],
        }
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load(self) -> tuple[list[Wurf], dict]:
        """
        Read JSON file from disk and deserialize back to Wurf entities and metadata.
        Returns empty list and default metadata if file does not exist yet.
        """
        if not os.path.exists(self._filepath):
            return [], {"players": [], "next_player_id": None}

        with open(self._filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        players = data.get("players", []) or []
        next_player_id = data.get("next_player_id")
        round_limit = data.get("round_limit")
        current_round = data.get("current_round", 1) or 1

        result = []
        for item in data.get("throws", []):
            wurf = Wurf(
                augenzahl=Augenzahl(item["wert"]),
                zeitstempel=datetime.fromisoformat(item["zeitstempel"]),
                id=item["id"],
                spieler_id=item.get("spieler_id"),
            )
            result.append(wurf)
        return result, {
            "players": players,
            "next_player_id": next_player_id,
            "round_limit": round_limit,
            "current_round": current_round,
        }

    def ist_persistent(self) -> bool:
        return True


class InMemoryWurfRepository(AbstractRepository):
    """
    Concrete repository — lives in the INFRASTRUCTURE layer.

    Stores throws in a Python list (RAM only).
    Data is lost when the program exits — perfect for development and testing.

    To switch to a real database: create PostgresWurfRepository(AbstractWurfRepository)
    with the same three methods. Zero changes to domain or application code.
    """

    def __init__(self):
        self._store: list[Wurf] = []
        self._meta = {
            "players": [],
            "next_player_id": None,
            "round_limit": None,
            "current_round": 1,
        }

    def speichern(self, wurf: Wurf) -> None:
        self._store.append(wurf)

    def alle(self) -> list[Wurf]:
        return list(self._store)

    def anzahl(self) -> int:
        return len(self._store)

    def ist_persistent(self) -> bool:
        return False

    def get_meta(self) -> dict:
        return {
            "players": list(self._meta["players"]),
            "next_player_id": self._meta["next_player_id"],
            "round_limit": self._meta["round_limit"],
            "current_round": self._meta["current_round"],
        }

    def set_meta(self, meta: dict) -> None:
        self._meta = {
            "players": list(meta.get("players", [])),
            "next_player_id": meta.get("next_player_id"),
            "round_limit": meta.get("round_limit"),
            "current_round": meta.get("current_round"),
        }
