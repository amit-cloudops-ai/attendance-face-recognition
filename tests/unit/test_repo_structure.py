from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_required_docs_exist():
    names = ["SPEC.md", "contracts.md", "STATUS.md", "AI_CONTEXT.md", "ARCHITECTURE.md", "TEAM_BRIEF.md"]
    for name in names:
        assert (ROOT / "docs" / name).exists(), f"missing docs/{name}"
