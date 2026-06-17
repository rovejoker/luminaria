"""Integration tests — verify all components work together.
Run OUTSIDE Docker: `cd luminaria && python test_integration.py`
"""
import sys
import os

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, ".")

def test_imports():
    """All modules should import without errors."""
    from app.config import MODEL_ID, OUTPUT_DIR, DATA_DIR, DURATION_OPTIONS
    from app.models import GenerateRequest, GenerateResponse, HistoryItem, HistoryList, ErrorResponse
    from app.database import init_db, insert_generation, get_history, get_generation, delete_generation
    print("[PASS] All modules imported successfully")

def test_models_validation():
    """Pydantic models should validate correctly."""
    from app.models import GenerateRequest

    # Valid request
    req = GenerateRequest(user_input="test prompt", duration=60)
    assert req.user_input == "test prompt"
    assert req.duration == 60

    # Invalid duration
    try:
        GenerateRequest(user_input="test", duration=999)
        assert False, "Should have raised validation error"
    except Exception:
        pass

    # Empty input
    try:
        GenerateRequest(user_input="", duration=60)
        assert False, "Should have raised validation error"
    except Exception:
        pass

    print("[PASS] Model validation works correctly")

def test_database():
    """Database CRUD operations should work."""
    from app.database import init_db, insert_generation, get_history, get_generation, delete_generation

    init_db()

    # Insert
    row_id = insert_generation("test input", "enhanced prompt", 60, "test.mp3", True)
    assert row_id > 0, f"Expected positive ID, got {row_id}"

    # Get by ID
    item = get_generation(row_id)
    assert item is not None
    assert item["user_input"] == "test input"
    assert item["prompt_enhanced"] == "enhanced prompt"
    assert item["duration"] == 60
    assert item["filename"] == "test.mp3"
    assert bool(item["enhanced"]) is True

    # Get history
    items = get_history()
    assert len(items) >= 1
    assert items[0]["id"] == row_id

    # Delete
    deleted = delete_generation(row_id)
    assert deleted is True

    # Verify deleted
    assert get_generation(row_id) is None

    # Delete non-existent
    assert delete_generation(99999) is False

    print("[PASS] Database CRUD operations work correctly")

def test_prompt_heuristic():
    """The professional prompt detection heuristic should work."""
    from app.prompt_enhancer import _is_likely_professional_prompt

    # Should detect professional prompts
    assert _is_likely_professional_prompt("piano ambient slow tempo 72 bpm reverb") is True
    assert _is_likely_professional_prompt("orchestral epic battle drums strings crescendo 140 bpm") is True

    # Should not flag natural language
    assert _is_likely_professional_prompt("温柔的钢琴曲") is False
    assert _is_likely_professional_prompt("make me some relaxing music") is False

    print("[PASS] Prompt heuristic works correctly")

def test_config_directories():
    """Config module should create required directories."""
    from app.config import OUTPUT_DIR, DATA_DIR
    assert os.path.isdir(OUTPUT_DIR), f"OUTPUT_DIR missing: {OUTPUT_DIR}"
    assert os.path.isdir(DATA_DIR), f"DATA_DIR missing: {DATA_DIR}"
    print(f"[PASS] Directories exist: output={os.path.basename(OUTPUT_DIR)}, data={os.path.basename(DATA_DIR)}")


if __name__ == "__main__":
    test_imports()
    test_models_validation()
    test_database()
    test_prompt_heuristic()
    test_config_directories()
    print("\n*** All integration tests passed! ***")
