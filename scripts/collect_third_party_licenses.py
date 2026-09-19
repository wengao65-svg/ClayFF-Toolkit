#!/usr/bin/env python3
"""Collect license evidence from the exact environment used for a binary build."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import sysconfig
from collections import deque
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


DEFAULT_ROOTS = ("ClayFF-Toolkit", "PyInstaller")
LICENSE_NAMES = ("license", "licence", "copying", "notice")
PROJECT_NAME = canonicalize_name("ClayFF-Toolkit")


def _distribution(name: str) -> metadata.Distribution:
    try:
        return metadata.distribution(name)
    except metadata.PackageNotFoundError as exc:
        raise RuntimeError(
            f"Required distribution {name!r} is not installed in the build environment."
        ) from exc


def _runtime_closure(roots: list[str]) -> list[metadata.Distribution]:
    queue = deque(roots)
    seen: set[str] = set()
    result: list[metadata.Distribution] = []

    while queue:
        requested = queue.popleft()
        dist = _distribution(requested)
        name = dist.metadata.get("Name", requested)
        canonical_name = canonicalize_name(name)
        if canonical_name in seen:
            continue
        seen.add(canonical_name)
        result.append(dist)

        for requirement_text in dist.requires or ():
            requirement = Requirement(requirement_text)
            if requirement.marker and not requirement.marker.evaluate({"extra": ""}):
                continue
            queue.append(requirement.name)

    return sorted(result, key=lambda item: canonicalize_name(item.metadata["Name"]))


def _license_label(dist: metadata.Distribution) -> str:
    expression = dist.metadata.get("License-Expression")
    if expression:
        return " ".join(expression.split())

    classifiers = dist.metadata.get_all("Classifier") or ()
    labels = [item.rsplit("::", 1)[-1].strip() for item in classifiers if "License ::" in item]
    if labels:
        return ", ".join(labels)

    value = dist.metadata.get("License")
    if value:
        first_line = next(
            (
                line.strip()
                for line in value.splitlines()
                if line.strip() and set(line.strip()) != {"="}
            ),
            "",
        )
        if first_line:
            return first_line[:160]

    return "Not declared in package metadata"


def _project_url(dist: metadata.Distribution) -> str:
    preferred = ("source", "repository", "homepage", "documentation")
    candidates: dict[str, str] = {}
    for value in dist.metadata.get_all("Project-URL") or ():
        if "," not in value:
            continue
        label, url = value.split(",", 1)
        candidates[label.strip().lower()] = url.strip()
    for label in preferred:
        if label in candidates:
            return candidates[label]
    return dist.metadata.get("Home-page") or next(iter(candidates.values()), "")


def _safe_file_name(value: str) -> str:
    value = value.replace("\\", "__").replace("/", "__").replace("..", "")
    return re.sub(r"[^A-Za-z0-9_.+-]", "_", value).strip("_") or "LICENSE.txt"


def _is_license_file(relative_path: Path) -> bool:
    lower_parts = [part.lower() for part in relative_path.parts]
    name = relative_path.name.lower()
    dist_info_license = any(
        part.endswith(".dist-info") and index + 1 < len(lower_parts) and lower_parts[index + 1] == "licenses"
        for index, part in enumerate(lower_parts)
    )
    return any(name.startswith(prefix) for prefix in LICENSE_NAMES) or dist_info_license


def _copy_distribution_licenses(
    dist: metadata.Distribution, destination: Path
) -> list[str]:
    copied: list[str] = []
    destination.mkdir(parents=True, exist_ok=True)

    for relative in dist.files or ():
        relative_path = Path(str(relative))
        if not _is_license_file(relative_path):
            continue
        source = Path(dist.locate_file(relative))
        if not source.is_file():
            continue
        target_name = _safe_file_name(str(relative_path))
        target = destination / target_name
        suffix = 2
        while target.exists() and target.read_bytes() != source.read_bytes():
            target = destination / f"{Path(target_name).stem}-{suffix}{Path(target_name).suffix}"
            suffix += 1
        if not target.exists():
            shutil.copy2(source, target)
        copied.append(target.name)

    return sorted(set(copied))


def _copy_python_license(licenses_dir: Path, repo_root: Path) -> str:
    version = ".".join(str(part) for part in sys.version_info[:3])
    major_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
    data_prefix = Path(sysconfig.get_path("data"))
    candidates = (
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE",
        Path(sys.prefix) / "LICENSE.txt",
        Path(sys.prefix) / "LICENSE",
        data_prefix / "LICENSE.txt",
        data_prefix / "LICENSE",
        Path("/usr/share/doc") / f"python{major_minor}" / "copyright",
        Path("/usr/share/doc") / f"python{major_minor}-minimal" / "copyright",
    )
    source = next((path for path in candidates if path.is_file()), None)
    if source is None:
        fallback = (
            repo_root
            / "packaging"
            / "windows"
            / "licenses"
            / "cpython"
            / f"{version}-LICENSE.txt"
        )
        if fallback.is_file():
            source = fallback
    if source is None:
        raise RuntimeError(
            "Could not find the CPython license in the interpreter or system documentation."
        )
    destination = licenses_dir / f"CPython-{version}"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination / source.name)
    return version


def _copy_supplemental_licenses(repo_root: Path, licenses_dir: Path) -> None:
    source_dir = repo_root / "packaging" / "windows" / "licenses"
    required = {
        "GPL-3.0-only.txt",
        "LGPL-3.0-only.txt",
        "PySide6-Qt-NOTICE.txt",
    }
    present = {path.name for path in source_dir.iterdir() if path.is_file()}
    missing = sorted(required - present)
    if missing:
        raise RuntimeError(f"Missing supplemental license files: {', '.join(missing)}")
    destination = licenses_dir / "PySide6-Qt"
    destination.mkdir(parents=True, exist_ok=True)
    for source in source_dir.iterdir():
        if source.is_file():
            shutil.copy2(source, destination / source.name)


def collect(output_dir: Path, roots: list[str], repo_root: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    licenses_dir = output_dir / "licenses"
    licenses_dir.mkdir(parents=True, exist_ok=True)

    python_version = _copy_python_license(licenses_dir, repo_root)
    _copy_supplemental_licenses(repo_root, licenses_dir)
    distributions = _runtime_closure(roots)

    dependency_lines = [f"CPython=={python_version}"]
    table_rows: list[tuple[str, str, str, str, str]] = []

    for dist in distributions:
        name = dist.metadata["Name"]
        version = dist.version
        dependency_lines.append(f"{name}=={version}")
        if canonicalize_name(name) == PROJECT_NAME:
            continue

        package_dir = licenses_dir / "Python-packages" / f"{name}-{version}"
        copied = _copy_distribution_licenses(dist, package_dir)
        if not copied:
            package_dir.mkdir(parents=True, exist_ok=True)
            (package_dir / "METADATA-LICENSE.txt").write_text(
                "No standalone license file was present in the installed wheel.\n"
                f"Package: {name}\n"
                f"Version: {version}\n"
                f"License metadata: {_license_label(dist)}\n"
                f"Project URL: {_project_url(dist)}\n",
                encoding="utf-8",
            )
            evidence = "package metadata; see supplemental notices where applicable"
        else:
            evidence = ", ".join(copied)
        table_rows.append((name, version, _license_label(dist), _project_url(dist), evidence))

    (output_dir / "DEPENDENCIES.txt").write_text(
        "\n".join(sorted(set(dependency_lines), key=str.casefold)) + "\n",
        encoding="utf-8",
    )

    notice_lines = [
        "# Binary dependency licenses",
        "",
        "This inventory was generated from the exact Python environment used to build",
        "this ClayFF-Toolkit binary. Raw license files copied from installed wheels are",
        "under `licenses/Python-packages`. CPython and PySide6/Qt notices are under",
        "their respective license directories.",
        "",
        "| Component | Version | Declared license | Project | Included evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, version, license_name, url, evidence in table_rows:
        safe = lambda value: value.replace("|", "\\|").replace("\n", " ")
        notice_lines.append(
            f"| {safe(name)} | {safe(version)} | {safe(license_name)} | "
            f"{safe(url)} | {safe(evidence)} |"
        )
    notice_lines.extend(
        [
            "",
            "The presence of a license text does not change the license of",
            "ClayFF-Toolkit or of any other component.",
        ]
    )
    (output_dir / "THIRD_PARTY_LICENSES.md").write_text(
        "\n".join(notice_lines) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--root", action="append", dest="roots")
    args = parser.parse_args()
    collect(args.output_dir, args.roots or list(DEFAULT_ROOTS), args.repo_root.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
