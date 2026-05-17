"""AITAPES CLI — IBM Bob entry point. Routes Bob invocations."""
from __future__ import annotations

import sys
from typing import Any


def run_bob_main(
    intent: str,
    *,
    source_dir: str = ".",
    auto_apply: bool = True,
    offline: bool = False,
) -> int:
    """Run the Bob pipeline with the given intent."""
    from aitapes.bob import BobConfig, BobSession
    from aitapes.plan import run_plan
    from aitapes.build import run_build
    from aitapes.bouncer import check_all

    try:
        run_plan(intent, "tapes-contract.json", "tapes-ledger.jsonl", offline=offline)
        output, report = run_build(
            contract_path="tapes-contract.json",
            source_dir=source_dir,
            output_path="tapes-patches.json",
            ledger_path="tapes-ledger.jsonl",
            auto_apply=False,
            offline=offline,
        )
        approved, remediations = check_all(list(output.patches), source_dir)
        for r in remediations:
            print(f"  [{r.action.upper()}] {r.original_file}: {r.reason}")
        if auto_apply and approved:
            from aitapes.patches import apply_patches
            results = apply_patches(source_dir, approved)
            print(f"  Applied {sum(1 for r in results if r.applied)}/{len(results)} patches")
        return 0
    except Exception as e:
        print(f"  Bob pipeline error: {e}")
        return 1


def run_chat_shell(source_dir: str = ".") -> None:
    """Launch the interactive chat shell."""
    from aitapes.tui import main as tui_shell
    tui_shell()


def main() -> None:
    """Main."""
    args = sys.argv[1:]
    intent = ""
    source_dir = "."
    auto_apply = True
    offline = False
    i = 0
    while i < len(args):
        if args[i] == "--intent" and i + 1 < len(args):
            intent = args[i + 1]; i += 2
        elif args[i] == "--source" and i + 1 < len(args):
            source_dir = args[i + 1]; i += 2
        elif args[i] == "--no-apply":
            auto_apply = False; i += 1
        elif args[i] == "--offline":
            offline = True; i += 1
        elif args[i] in ("--help", "-h"):
            print("Usage: tapes-bob --intent <text> [--source <dir>] [--no-apply] [--offline]")
            sys.exit(0)
        else:
            i += 1

    if not intent:
        print("Error: --intent is required")
        sys.exit(1)

    code = run_bob_main(intent, source_dir=source_dir, auto_apply=auto_apply, offline=offline)
    sys.exit(code)


if __name__ == "__main__":
    main()
