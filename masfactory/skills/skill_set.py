from dataclasses import dataclass, field

from .skill import Skill


@dataclass(frozen=True)
class SkillSet:
    """Skill-side composition view consumed by Agents."""

    skills: list[Skill] = field(default_factory=list)
    _rendered_instructions: str | None = field(default=None, init=False, repr=False)
    _metadata: list[dict[str, object]] | None = field(default=None, init=False, repr=False)

    def render_instructions(self) -> str:
        cached = self._rendered_instructions
        if cached is not None:
            return cached
        if not self.skills:
            rendered = ""
        else:
            skill_sections = "\n\n".join(skill.render_section() for skill in self.skills)
            rendered = f"[Loaded Skills]\n\n{skill_sections}"
        object.__setattr__(self, "_rendered_instructions", rendered)
        return rendered

    def compose(self, base_instructions: str) -> str:
        rendered = self.render_instructions()
        if not rendered:
            return base_instructions
        return f"{base_instructions}\n\n{rendered}"

    def metadata(self) -> list[dict[str, object]]:
        cached = self._metadata
        if cached is not None:
            return cached
        metadata = [skill.metadata() for skill in self.skills]
        object.__setattr__(self, "_metadata", metadata)
        return metadata
