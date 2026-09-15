# J Launcher metadata

This repository is the metadata endpoint used by J Launcher:

`https://jom3a-j.github.io/J-Launcher-meta-launcher/`

J Launcher owns this endpoint. Prism Launcher metadata is imported as the
compatibility baseline so legacy Minecraft and loader versions keep working.
J-owned metadata files in `overrides/` are then applied on top and always win.

## Add J-owned metadata

Place a complete launcher metadata file at:

```text
overrides/<package uid>/<version>.json
```

For example:

```text
overrides/net.minecraftforge/65.1.1.json
```

The file must contain matching `uid` and `version` fields plus `releaseTime`.
The refresh tool adds or replaces the package index entry and recalculates both
the version and package SHA-256 values. Do not edit generated root package
indexes by hand.

## Refresh

Run:

```text
python tools/refresh_metadata.py --upstream <Prism meta-launcher checkout> --destination .
python -m unittest discover -s tools/tests -p "test_*.py"
```

The scheduled GitHub workflow performs the same refresh daily and can also be
started manually. It commits only when generated metadata changes.
