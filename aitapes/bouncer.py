"""TAPES Bouncer — invariant enforcement with governed repair.

When a protected file is touched, the Bouncer redirects the patch
to a safe extension file instead of just blocking.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aitapes.patches import Patch, _find_symbol_in_ast

# Protected files mapped to safe redirect targets
PROTECTED_FILES: dict[str, str] = {
    "legacy_auth.py": "auth_middleware_extension.py",
    "payment.py": "payment_extension.py",
    "config.py": "config_extension.py",
}

# Max files a single patch session may touch before intercept
MAX_MUTATION_FILES = 3


@dataclass
class RemediationAction:
    """Remediationaction."""
    action: str  # "redirect" or "reject"
    original_file: str
    redirect_target: str = ""
    reason: str = ""


def check_all(patches: list[Patch], source_dir: str = ".") -> tuple[list[Patch], list[RemediationAction]]:
    """Run gates. Returns (approved_patches, remediation_actions)."""
    approved: list[Patch] = []
    remediations: list[RemediationAction] = []

    # Mutation boundary gate: too many files touched
    touched = {p.file for p in patches}
    if len(touched) > MAX_MUTATION_FILES:
        for p in patches:
            remediations.append(RemediationAction(
                action="reject",
                original_file=p.file,
                reason=f"Mutation boundary exceeded: touches {len(touched)} files (max {MAX_MUTATION_FILES})",
            ))
        return approved, remediations

    for p in patches:
        # Check protected files FIRST (skip gates for original, redirect instead)
        if p.file in PROTECTED_FILES:
            target = PROTECTED_FILES[p.file]
            # Create a new patch targeting the redirect file
            redirected = Patch(
                file=target,
                target_symbol=p.target_symbol,
                search=p.search,
                replace=p.replace,
                reasoning=f"{p.reasoning} (redirected from {p.file})",
            )
            # Run gates on the redirected patch
            rgates = _check_gates(redirected, source_dir)
            if all(rgates.values()):
                remediations.append(RemediationAction(
                    action="redirect",
                    original_file=p.file,
                    redirect_target=target,
                    reason=f"Protected file {p.file} — redirected to {target}",
                ))
                approved.append(redirected)
            else:
                failed = [k for k, v in rgates.items() if not v]
                remediations.append(RemediationAction(
                    action="reject",
                    original_file=p.file,
                    reason=f"Protected file {p.file} — redirect failed gates: {', '.join(failed)}",
                ))
            continue

        gates = _check_gates(p, source_dir)
        if all(gates.values()):
            approved.append(p)
        else:
            failed = [k for k, v in gates.items() if not v]
            remediations.append(RemediationAction(
                action="reject",
                original_file=p.file,
                reason=f"Gate(s) failed: {', '.join(failed)}",
            ))

    return approved, remediations


def _check_gates(patch: Patch, source_dir: str) -> dict[str, bool]:
    """ Check Gates."""
    result = {"syntax": True, "boundary": True, "anchor": True, "match": True, "integrity": True}

    try:
        ast.parse(patch.replace)
    except SyntaxError:
        try:
            ast.parse("def _():\n" + patch.replace)
        except SyntaxError:
            result["syntax"] = False

    target = (Path(source_dir) / patch.file).resolve()
    if not str(target).startswith(str(Path(source_dir).resolve())):
        result["boundary"] = False

    filepath = Path(source_dir) / patch.file
    if filepath.exists():
        try:
            source = filepath.read_text(encoding="utf-8")
            if not _find_symbol_in_ast(source, patch.target_symbol):
                result["anchor"] = False
        except (OSError, SyntaxError):
            result["anchor"] = False

    if filepath.exists():
        source = filepath.read_text(encoding="utf-8")
        count = source.count(patch.search)
        if count != 1:
            result["match"] = False

    if len(patch.replace) > len(patch.search) * 10 and len(patch.search) > 0:
        result["integrity"] = False

    return result
