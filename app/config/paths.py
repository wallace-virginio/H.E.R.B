"""Caminhos padrão do projeto H.E.R.B."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    """Árvore de diretórios do projeto."""

    root: Path
    app: Path
    assets: Path
    data: Path
    memory: Path
    speakers: Path
    cache: Path
    logs: Path
    config_file: Path
    personality_file: Path
    env_file: Path

    @classmethod
    def from_root(cls, root: Path | None = None) -> "Paths":
        root = (root or Path(__file__).resolve().parents[2]).resolve()
        data = root / "data"
        return cls(
            root=root,
            app=root / "app",
            assets=root / "assets",
            data=data,
            memory=data / "memory",
            speakers=data / "speakers",
            cache=data / "cache",
            logs=root / "logs",
            config_file=data / "config.json",
            personality_file=root / "app" / "config" / "personality.yaml",
            env_file=root / ".env",
        )

    def ensure(self) -> None:
        """Garante que os diretórios essenciais existam."""
        for path in (self.data, self.memory, self.speakers, self.cache, self.logs):
            path.mkdir(parents=True, exist_ok=True)


_paths: Paths | None = None


def get_paths(root: Path | None = None) -> Paths:
    global _paths
    if _paths is None or root is not None:
        _paths = Paths.from_root(root)
        _paths.ensure()
    return _paths
