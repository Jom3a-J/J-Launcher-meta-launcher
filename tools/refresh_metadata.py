#!/usr/bin/env python3
"""Refresh J Launcher metadata from its legacy baseline and J-owned overrides."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


UID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
INDEX_FIELDS = (
    "version",
    "releaseTime",
    "type",
    "recommended",
    "volatile",
    "requires",
    "conflicts",
)


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=4) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_uids(index: dict, source: Path) -> list[str]:
    packages = index.get("packages")
    if not isinstance(packages, list):
        raise ValueError(f"Expected a packages array in {source / 'index.json'}")
    result: list[str] = []
    for package in packages:
        uid = package.get("uid") if isinstance(package, dict) else None
        if not isinstance(uid, str) or not UID_PATTERN.fullmatch(uid):
            raise ValueError(f"Unsafe or missing package uid in {source / 'index.json'}")
        result.append(uid)
    return result


def copy_legacy_baseline(upstream: Path, destination: Path) -> dict:
    upstream_index = read_json(upstream / "index.json")
    upstream_uids = package_uids(upstream_index, upstream)

    previous_uids: list[str] = []
    destination_index = destination / "index.json"
    if destination_index.is_file():
        previous_uids = package_uids(read_json(destination_index), destination)

    for uid in sorted(set(previous_uids) | set(upstream_uids)):
        target = destination / uid
        if target.exists():
            shutil.rmtree(target)
        source = upstream / uid
        if source.is_dir():
            shutil.copytree(source, target)

    shutil.copy2(upstream / "index.json", destination_index)
    nojekyll = upstream / ".nojekyll"
    if nojekyll.is_file():
        shutil.copy2(nojekyll, destination / ".nojekyll")
    return upstream_index


def apply_overrides(destination: Path, root_index: dict) -> int:
    overrides_root = destination / "overrides"
    if not overrides_root.is_dir():
        return 0

    root_packages = {
        package["uid"]: package
        for package in root_index["packages"]
        if isinstance(package, dict) and isinstance(package.get("uid"), str)
    }
    changed_packages: set[str] = set()
    applied = 0

    for override in sorted(overrides_root.glob("*/*.json")):
        uid = override.parent.name
        if not UID_PATTERN.fullmatch(uid) or uid not in root_packages:
            raise ValueError(f"Override uses an unknown or unsafe package uid: {uid}")

        metadata = read_json(override)
        version = metadata.get("version")
        if metadata.get("uid") != uid:
            raise ValueError(f"Override uid does not match its directory: {override}")
        if not isinstance(version, str) or not version or Path(version).name != version:
            raise ValueError(f"Override has an unsafe or missing version: {override}")
        if not isinstance(metadata.get("releaseTime"), str):
            raise ValueError(f"Override is missing releaseTime: {override}")

        package_directory = destination / uid
        package_index_path = package_directory / "index.json"
        package_index = read_json(package_index_path)
        published_version = package_directory / f"{version}.json"
        shutil.copy2(override, published_version)

        entry = {
            field: metadata[field]
            for field in INDEX_FIELDS
            if field in metadata
        }
        entry["sha256"] = sha256(published_version)
        versions = package_index.get("versions")
        if not isinstance(versions, list):
            raise ValueError(f"Expected a versions array in {package_index_path}")
        versions = [
            existing for existing in versions
            if not isinstance(existing, dict) or existing.get("version") != version
        ]
        versions.append(entry)
        versions.sort(
            key=lambda item: (
                item.get("releaseTime", "") if isinstance(item, dict) else "",
                item.get("version", "") if isinstance(item, dict) else "",
            ),
            reverse=True,
        )
        package_index["versions"] = versions
        write_json(package_index_path, package_index)
        changed_packages.add(uid)
        applied += 1

    for uid in sorted(changed_packages):
        root_packages[uid]["sha256"] = sha256(destination / uid / "index.json")
    if changed_packages:
        write_json(destination / "index.json", root_index)
    return applied


def refresh(upstream: Path, destination: Path) -> int:
    upstream = upstream.resolve()
    destination = destination.resolve()
    if upstream == destination:
        raise ValueError("Upstream and destination must be different directories")
    if not (upstream / "index.json").is_file():
        raise ValueError(f"Upstream metadata index is missing: {upstream}")
    if not destination.is_dir():
        raise ValueError(f"Destination repository is missing: {destination}")

    root_index = copy_legacy_baseline(upstream, destination)
    return apply_overrides(destination, root_index)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    arguments = parser.parse_args()
    applied = refresh(arguments.upstream, arguments.destination)
    print(f"Metadata refresh complete; applied {applied} J-owned override(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
