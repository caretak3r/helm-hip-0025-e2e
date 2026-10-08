"""The charts of a run as a Helm chart repository: runs/<stamp>/charts/.

Each archive holds the files of one chart directory byte for byte, so a reader can inspect
and install the chart that the tests installed. `helm package` is not used: the tier
binaries stop with `invalid chart apiVersion` for a chart v3, and for a chart v2 they write
Chart.yaml again from the fields that they know, which drops `depends-on`.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import tarfile
from pathlib import Path

import yaml


def chart_files(chart: Path) -> list[Path]:
    """The files that helm loads from a chart directory, relative to it, in a fixed order."""
    if (chart / ".helmignore").exists():
        raise ValueError(f"{chart}: .helmignore is not supported; an archive must hold the files that helm loads")
    files = []
    for path in chart.rglob("*"):
        rel = path.relative_to(chart)
        # helm's default ignore rule `templates/.?*`: it skips dotfiles directly in templates/
        hidden = rel.parts[0] == "templates" and len(rel.parts) > 1 and len(rel.parts[1]) > 1 \
            and rel.parts[1].startswith(".")
        if path.is_file() and not hidden:
            files.append(rel)
    return sorted(files, key=Path.as_posix)


def pack(chart: Path) -> tuple[dict, bytes]:
    """Chart.yaml and a .tgz of the chart directory. The same files always give the same bytes."""
    meta = yaml.safe_load((chart / "Chart.yaml").read_text())
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0) as gz, \
            tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for rel in chart_files(chart):
            data = (chart / rel).read_bytes()
            info = tarfile.TarInfo(f"{meta['name']}/{rel.as_posix()}")  # owner root, mtime 0
            info.size, info.mode = len(data), 0o644
            tar.addfile(info, io.BytesIO(data))
    return meta, buf.getvalue()


def publish(charts: Path, dest: Path, created: str) -> list[dict]:
    """Write one archive for each chart directory in `charts`, and index.yaml, to `dest`.

    The index uses relative URLs, so the repository works from any address. Returns the
    records that run.json keeps: chart directory -> archive and digest.
    """
    dest.mkdir(parents=True)
    records: list[dict] = []
    entries: dict[str, list[dict]] = {}
    for chart in sorted(p for p in charts.iterdir() if (p / "Chart.yaml").is_file()):
        meta, data = pack(chart)
        name, version = meta["name"], str(meta["version"])
        archive = f"{name}-{version}.tgz"
        if (dest / archive).exists():
            raise ValueError(f"{chart}: another chart directory also gives {archive}")
        (dest / archive).write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        records.append({"source": f"{charts.name}/{chart.name}", "name": name, "version": version,
                        "apiVersion": meta["apiVersion"], "archive": archive, "sha256": digest})
        entries.setdefault(name, []).append({
            "apiVersion": meta["apiVersion"], "name": name, "version": version,
            "description": meta.get("description", ""), "created": created, "digest": digest, "urls": [archive],
        })
    index = {"apiVersion": "v1", "entries": entries, "generated": created}
    (dest / "index.yaml").write_text(yaml.safe_dump(index, sort_keys=False))
    return records
