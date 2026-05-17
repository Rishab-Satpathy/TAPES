"""Skills Manifest for AITAPES v8.0.

Skills are capability overlays that enable tool subsets based on context.
NOT autonomous agents — they do NOT orchestrate or make decisions.
The TAPES kernel always controls workflow, permissions, rollback, and execution ordering.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class SkillCategory(StrEnum):
    """Categories of skills."""
    FRONTEND = "frontend"
    BACKEND = "backend"
    INFRA = "infra"
    SECURITY = "security"
    BLENDER = "blender"


@dataclass
class SkillManifest:
    """Manifest for a skill with enabled tools and capabilities."""
    name: str
    category: SkillCategory
    description: str
    enabled_tools: list[str] = field(default_factory=list)
    disabled_tools: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_tool_enabled(self, tool_name: str) -> bool:
        """Check if a tool is enabled by this skill."""
        if tool_name in self.disabled_tools:
            return False
        if self.enabled_tools:
            return tool_name in self.enabled_tools
        return True


# ── Built-in Skills ────────────────────────────────────────────────────────────

FRONTEND_SKILL = SkillManifest(
    name="frontend",
    category=SkillCategory.FRONTEND,
    description="Frontend development skill: React, Vue, CSS, HTML, bundlers",
    enabled_tools=["fs_read", "fs_write", "fs_list"],
    capabilities=["react", "vue", "css", "html", "webpack", "vite"],
    metadata={"version": "1.0", "tier": "built-in"},
)

BACKEND_SKILL = SkillManifest(
    name="backend",
    category=SkillCategory.BACKEND,
    description="Backend development skill: APIs, databases, servers",
    enabled_tools=["fs_read", "fs_write", "fs_list", "shell_run"],
    capabilities=["api", "database", "server", "python", "nodejs"],
    metadata={"version": "1.0", "tier": "built-in"},
)

INFRA_SKILL = SkillManifest(
    name="infra",
    category=SkillCategory.INFRA,
    description="Infrastructure skill: Docker, Kubernetes, cloud deploys",
    enabled_tools=["fs_read", "fs_list", "docker_build", "docker_run", "docker_push", "git_status"],
    capabilities=["docker", "kubernetes", "aws", "gcp", "azure", "terraform"],
    metadata={"version": "1.0", "tier": "built-in"},
)

SECURITY_SKILL = SkillManifest(
    name="security",
    category=SkillCategory.SECURITY,
    description="Security skill: auditing, hardening, compliance",
    enabled_tools=["fs_read", "fs_list"],
    capabilities=["audit", "hardening", "compliance", "owasp", "pentest"],
    metadata={"version": "1.0", "tier": "built-in"},
)

BLENDER_SKILL = SkillManifest(
    name="blender",
    category=SkillCategory.BLENDER,
    description="Blender 3D skill: modeling, animation, rendering",
    enabled_tools=["fs_read", "fs_write", "fs_list"],
    capabilities=["blender", "3d", "modeling", "animation", "rendering", "cycles"],
    metadata={"version": "1.0", "tier": "built-in"},
)

BUILTIN_SKILLS = [FRONTEND_SKILL, BACKEND_SKILL, INFRA_SKILL, SECURITY_SKILL, BLENDER_SKILL]


class SkillRegistry:
    """Registry of available skills."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillManifest] = {}
        self._active_skills: list[str] = []

    def register(self, skill: SkillManifest) -> None:
        """Register a skill."""
        self._skills[skill.name] = skill
        logger.info("Registered skill: %s (%s)", skill.name, skill.category.value)

    def get(self, name: str) -> SkillManifest | None:
        """Get a skill by name."""
        return self._skills.get(name)

    def activate(self, name: str) -> bool:
        """Activate a skill for the current session."""
        if name not in self._skills:
            logger.warning("Unknown skill: %s", name)
            return False
        if name not in self._active_skills:
            self._active_skills.append(name)
            logger.info("Activated skill: %s", name)
        return True

    def deactivate(self, name: str) -> bool:
        """Deactivate a skill."""
        if name in self._active_skills:
            self._active_skills.remove(name)
            logger.info("Deactivated skill: %s", name)
            return True
        return False

    def get_active_skills(self) -> list[SkillManifest]:
        """Get all active skills."""
        return [self._skills[name] for name in self._active_skills if name in self._skills]

    def is_tool_enabled_for_any_active(self, tool_name: str) -> bool:
        """Check if a tool is enabled by any active skill."""
        for skill in self.get_active_skills():
            if skill.is_tool_enabled(tool_name):
                return True
        return False

    def list_skills(self) -> list[str]:
        """List all registered skill names."""
        return list(self._skills.keys())


_skill_registry = SkillRegistry()


def get_skill_registry() -> SkillRegistry:
    """Get the global skill registry."""
    return _skill_registry


def init_builtin_skills() -> None:
    """Initialize all built-in skills."""
    for skill in BUILTIN_SKILLS:
        _skill_registry.register(skill)
    logger.info("Initialized %d built-in skills", len(BUILTIN_SKILLS))


init_builtin_skills()