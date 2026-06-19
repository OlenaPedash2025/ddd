from abc import ABC, abstractmethod

from domain.entities import Wurf


class AbstractRepository(ABC):
    """
    Abstract repository interface — lives in the DOMAIN layer.

    Defines the CONTRACT that every storage implementation must fulfil.
    The domain knows WHAT operations exist, but not HOW they are implemented.

    This is the Dependency Inversion Principle:
        Domain defines the interface (abstract)
        Infrastructure implements it (concrete)
        Application uses only the interface (never the concrete class)
    """

    @abstractmethod
    def speichern(self, wurf: Wurf) -> None:
        """Save a Wurf entity to the repository."""
        pass

    @abstractmethod
    def alle(self) -> list[Wurf]:
        """Retrieve all Wurf entities from the repository."""
        pass

    @abstractmethod
    def anzahl(self) -> int:
        """Return the total number of Wurf entities in the repository."""
        pass

    @abstractmethod
    def ist_persistent(self) -> bool:
        """Returns True if this repository persists data between sessions."""
        pass

    @abstractmethod
    def get_meta(self) -> dict:
        """Return saved game metadata such as players and next player."""
        pass

    @abstractmethod
    def set_meta(self, meta: dict) -> None:
        """Save game metadata such as players and next player."""
        pass


class AbstractFileWurfRepository(AbstractRepository):
    """
    Base class for all file-based repositories (JSON, YAML, XML).
    Adds file loading capability on top of the abstract contract.
    """

    def __init__(self):
        self._meta = {
            "players": [],
            "next_player_id": None,
            "round_limit": None,
            "current_round": 1,
        }

    def _save(self) -> None:
        """Serialize and write data to file. Must be implemented by subclass."""
        ...
        pass

    @abstractmethod
    def _load(self) -> tuple[list[Wurf], dict]:
        """Read and deserialize data from file. Must be implemented by subclass."""
        ...
        pass

    def laden(self) -> None:
        """Load existing data from file into internal store."""
        self._store, self._meta = self._load()

    def speichern(self, wurf: Wurf) -> None:
        """Save a single throw — appends to list and writes entire file."""
        self._store.append(wurf)
        self._save()

    def alle(self) -> list[Wurf]:
        """Return all stored throws as a copy."""
        return list(self._store)

    def anzahl(self) -> int:
        """Return total count of stored throws."""
        return len(self._store)

    def get_meta(self) -> dict:
        """Return a copy of the currently loaded game metadata."""
        return {
            "players": list(self._meta.get("players", [])),
            "next_player_id": self._meta.get("next_player_id"),
            "round_limit": self._meta.get("round_limit"),
            "current_round": self._meta.get("current_round"),
        }

    def set_meta(self, meta: dict) -> None:
        """Update game metadata and persist the file."""
        self._meta = {
            "players": list(meta.get("players", [])),
            "next_player_id": meta.get("next_player_id"),
            "round_limit": meta.get("round_limit"),
            "current_round": meta.get("current_round"),
        }
        self._save()
