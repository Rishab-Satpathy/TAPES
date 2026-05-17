from forest_tapes.tapes_core.representations import (
    build_ast_window,
    build_execution_trace,
    build_component_hierarchy,
    build_data_flow_graph,
)


def test_build_ast_window_extracts_functions() -> None:
    source = """
def hello():
    pass

def world():
    pass

class Foo:
    def bar(self):
        pass
"""
    window = build_ast_window(source, "test.py", target_line=5, window_lines=20)
    assert "hello" in window.functions
    assert "world" in window.functions
    assert "Foo" in window.classes


def test_build_ast_window_clips_lines() -> None:
    source = "\n".join([f"line {i}" for i in range(100)])
    window = build_ast_window(source, "test.py", target_line=50, window_lines=10)
    assert len(window.lines) == 10
    assert window.start_line >= 44
    assert window.start_line <= 46
    assert window.end_line >= 54
    assert window.end_line <= 56


def test_build_execution_trace() -> None:
    frames = [
        {"function": "main", "file_path": "app.py", "line_number": 10},
        {"function": "process", "file_path": "utils.py", "line_number": 25},
    ]
    trace = build_execution_trace(frames, error="ValueError")
    assert len(trace.frames) == 2
    assert trace.frames[0].function == "main"
    assert trace.error == "ValueError"


def test_build_component_hierarchy() -> None:
    source = """
class UserService:
    def login(self):
        pass
    def logout(self):
        pass

def helper():
    pass
"""
    hierarchy = build_component_hierarchy(source, "module")
    assert hierarchy.root.name == "module"
    assert len(hierarchy.all_nodes) >= 2  # UserService + helper


def test_build_data_flow_graph() -> None:
    source = """
def process(input_data):
    result = transform(input_data)
    return result
"""
    graph = build_data_flow_graph(source)
    assert len(graph.sources) > 0 or len(graph.sinks) > 0
