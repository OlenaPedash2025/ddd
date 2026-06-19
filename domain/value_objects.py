from dataclasses import dataclass


@dataclass(frozen=True)
class Augenzahl:
    """
    Value Object: represents the face value of a single dice roll.

    Rules (enforced here, nowhere else):
    - Must be an integer
    - Must be between 1 and 6 inclusive

    Two Augenzahl objects with the same value are always equal:
        Augenzahl(4) == Augenzahl(4)  →  True
    """

    wert: int

    def __post_init__(self):
        """
        dataclass calls this automatically right after __init__.
        This is where we enforce business rules.
        If a rule is broken, the object is never created — it's impossible
        to have an invalid Augenzahl in the system.
        """

        if not isinstance(self.wert, int):
            raise TypeError("Die Augenzahl muss eine ganze Zahl sein.")

        if not (1 <= self.wert <= 6):
            raise ValueError(
                "Die Augenzahl muss eine ganze Zahl zwischen 1 und 6 sein."
            )

    def __str__(self):
        return f"Augenzahl({self.wert})"


@dataclass(frozen=True)
class Spielername:
    """
    Value Object: represents the name of a player.

    Rules:
    - Must be a non-empty string
    - Must be at least 3 characters long
    - Must not contain only whitespace

    Two Spielername objects with the same value are always equal:
        Spielername("Alice") == Spielername("Alice")  →  True
    """

    name: str

    def __post_init__(self):
        if not isinstance(self.name, str):
            raise TypeError("Der Spielername muss eine Zeichenkette sein.")

        if len(self.name.strip()) < 3:
            raise ValueError("Der Spielername muss mindestens 3 Zeichen lang sein.")

        if not self.name.strip().isalpha():
            raise ValueError(
                "Der Spielername darf nur Buchstaben enthalten, keine Zahlen oder Sonderzeichen."
            )

    def __str__(self):
        return f"Spielername({self.name})"


@dataclass(frozen=True)
class AnzahlSpieler:
    """
    Value Object: represents the number of players in a game.

    Rules:
    - Must be an integer
    - Must be between 1 and 99 inclusive

    Two AnzahlSpieler objects with the same value are always equal:
        AnzahlSpieler(4) == AnzahlSpieler(4)  →  True
    """

    anzahl: int

    def __post_init__(self):
        if not isinstance(self.anzahl, int):
            raise TypeError("Die Anzahl der Spieler muss eine ganze Zahl sein.")

        if not (1 <= self.anzahl <= 99):
            raise ValueError("Die Anzahl der Spieler muss zwischen 1 und 99 liegen.")

    def __str__(self):
        return f"AnzahlSpieler({self.anzahl})"
