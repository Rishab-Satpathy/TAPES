from pathlib import Path

from forest_tapes.tapes_core.forest_graph import (
    build_forest_graph,
    get_neighborhood,
    estimate_blast_radius,
)


def test_build_forest_graph_from_directory(tmp_path) -> None:
    # Create test files
    (tmp_path / "module_a.py").write_text("import module_b\ndef hello(): pass\n")
    (tmp_path / "module_b.py").write_text("def world(): pass\n")

    graph = build_forest_graph(str(tmp_path))
    assert len(graph.files) == 2
    assert len(graph.edges) >= 1


def test_get_neighborhood() -> None:
    (tmp_path := Path("test_neighborhood")).mkdir(exist_ok=True)
    try:
        (tmp_path / "a.py").write_text("import b\n")
        (tmp_path / "b.py").write_text("import c\n")
        (tmp_path / "c.py").write_text("pass\n")

        graph = build_forest_graph(str(tmp_path))
        neighbors = get_neighborhood(graph, "a", radius=1)
        assert "b" in neighbors
    finally:
        import shutil
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_estimate_blast_radius() -> None:
    (tmp_path := Path("test_blast")).mkdir(exist_ok=True)
    try:
        (tmp_path / "core.py").write_text("pass\n")
        (tmp_path / "a.py").write_text("import core\n")
        (tmp_path / "b.py").write_text("import core\n")

        graph = build_forest_graph(str(tmp_path))
        radius = estimate_blast_radius(graph, "core.py")
        assert radius == 2
    finally:
        import shutil
        shutil.rmtree(tmp_path, ignore_errors=True)
