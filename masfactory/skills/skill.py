from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SKILL_TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}
_MAX_SKILL_SUPPORTING_FILES = 1
_MAX_SKILL_TEXT_LENGTH = 4096


def _read_skill_text(path: Path) -> str | None:
    if path.suffix.lower() not in _SKILL_TEXT_EXTENSIONS:
        return None
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    if len(text) > _MAX_SKILL_TEXT_LENGTH:
        return f"{text[:_MAX_SKILL_TEXT_LENGTH].rstrip()}\n..."
    return text


@dataclass(frozen=True)
class Skill:
    """Parsed Anthropic-style SKILL.md package used by MASFactory agents.

    A Skill is a lightweight, instruction-centered asset loaded from a directory.
    It preserves the parsed `SKILL.md` body plus discovered supporting files such as
    templates, examples, references, and scripts.
    """

    __node_template_scope__ = "shared"

    name: str
    description: str | None
    body: str
    skill_dir: Path
    skill_md_path: Path
    frontmatter: dict[str, Any] = field(default_factory=dict)
    examples: list[Path] = field(default_factory=list)
    templates: list[Path] = field(default_factory=list)
    references: list[Path] = field(default_factory=list)
    scripts: list[Path] = field(default_factory=list)
    raw_markdown: str = ""

    @property
    def source_path(self) -> str:
        """Return the normalized source directory for this skill package."""
        return str(self.skill_dir)

    def metadata(self) -> dict[str, object]:
        """Return stable metadata used by Agent/visualizer integrations."""
        return {
            "name": self.name,
            "description": self.description,
            "source_path": self.source_path,
        }

    def render_supporting_files(self, label: str, paths: list[Path]) -> str | None:
        """Render a limited number of supporting files for prompt inclusion."""
        rendered: list[str] = []
        for path in paths[:_MAX_SKILL_SUPPORTING_FILES]:
            text = _read_skill_text(path)
            if text:
                rendered.append(f"### {label}: {path.name}\n{text}")
        if not rendered:
            return None
        return "\n\n".join(rendered)

    def render_section(self) -> str:
        """Render one skill as a prompt section for Agent directives."""
        parts: list[str] = [f"## Skill: {self.name}"]
        if self.description:
            parts.append(f"Description: {self.description}")
        parts.append(self.body)

        template_section = self.render_supporting_files("Template", self.templates)
        if template_section:
            parts.append(template_section)

        example_section = self.render_supporting_files("Example", self.examples)
        if example_section:
            parts.append(example_section)

        return "\n\n".join(part for part in parts if part.strip())
