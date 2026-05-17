from forest_tapes.tapes_core.runtime_observer import RuntimeObserver
from forest_tapes.tapes_core.pressure_kernel import RuntimeSignals


def test_observer_records_patch_attempts() -> None:
    observer = RuntimeObserver()
    observer.record_patch_attempt(success=True)
    observer.record_patch_attempt(success=False)
    signals = observer.get_signals()
    assert signals.patch_attempts == 2
    assert signals.patch_failures == 1


def test_observer_records_broad_rewrite() -> None:
    observer = RuntimeObserver()
    observer.record_broad_rewrite()
    signals = observer.get_signals()
    assert signals.broad_rewrite_attempted is True


def test_observer_records_contradictions() -> None:
    observer = RuntimeObserver()
    observer.record_contradiction("A conflicts with B")
    observer.record_contradiction("A conflicts with B")  # duplicate
    observer.record_contradiction("C conflicts with D")
    signals = observer.get_signals()
    assert signals.contradiction_count == 2


def test_observer_records_representation_switches() -> None:
    observer = RuntimeObserver()
    observer.record_representation_switch("AST_SOURCE_WINDOW")
    observer.record_representation_switch("AST_SOURCE_WINDOW")  # same
    observer.record_representation_switch("TOPOLOGY_GRAPH")
    signals = observer.get_signals()
    assert signals.representation_switches == 1


def test_observer_records_hallucinations() -> None:
    observer = RuntimeObserver()
    observer.record_hallucinated_import("fake_module")
    observer.record_hallucinated_import("fake_module")  # duplicate
    observer.record_hallucinated_api("fake.api()")
    summary = observer.summary()
    assert summary["hallucinated_imports"] == 1
    assert summary["hallucinated_apis"] == 1


def test_observer_reset() -> None:
    observer = RuntimeObserver()
    observer.record_patch_attempt(success=False)
    observer.record_syntax_failure()
    observer.reset()
    signals = observer.get_signals()
    assert signals.patch_attempts == 0
    assert signals.patch_failures == 0


def test_observer_summary() -> None:
    observer = RuntimeObserver()
    observer.record_patch_attempt(success=True)
    observer.record_assumption("inferred type")
    summary = observer.summary()
    assert summary["patch_attempts"] == 1
    assert summary["assumptions_made"] == 1
