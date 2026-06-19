import os


class SpielstandFinder:
    """Utility class to find existing game state files in the current directory."""

    EXPECTED_FILES = [".json", ".yaml", ".xml"]

    def finde_alle(self) -> list[str]:
        """Search for existing game state files in the current directory."""
        found_files = []
        for filename in os.listdir("."):
            if any(filename.endswith(ext) for ext in self.EXPECTED_FILES):
                found_files.append(filename)

        found_files.sort(
            key=lambda f: os.path.getmtime(f), reverse=True
        )  # sort alphabetically for consistent order
        return found_files
