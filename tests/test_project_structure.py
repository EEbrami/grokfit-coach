"""Basic structural tests for the initial project skeleton."""

from __future__ import annotations

from pathlib import Path
import unittest


class TestProjectStructure(unittest.TestCase):
    """Validate required files and directories exist."""

    def test_required_directories_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        expected = [
            root / "src" / "grokfit_coach" / "models",
            root / "src" / "grokfit_coach" / "rag",
            root / "src" / "grokfit_coach" / "tools",
            root / "src" / "grokfit_coach" / "agents",
            root / "src" / "grokfit_coach" / "ui",
            root / "src" / "grokfit_coach" / "utils",
            root / "src" / "grokfit_coach" / "evaluation",
            root / "tests",
            root / "docs",
        ]
        for path in expected:
            with self.subTest(path=path):
                self.assertTrue(path.is_dir())

    def test_required_files_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        expected = [
            root / ".gitignore",
            root / "LICENSE",
            root / "README.md",
            root / "requirements.txt",
            root / "PHASE_1_HANDOFF.md",
        ]
        for path in expected:
            with self.subTest(path=path):
                self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
