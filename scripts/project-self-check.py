#!/usr/bin/env python3
# Reject duplicate YAML keys in critical inventory variable files.

from pathlib import Path
import sys
import yaml


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def construct_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key: {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    construct_mapping,
)

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
files = [root / "inventory/production/group_vars/all/main.yml"]

failed = False
for path in files:
    try:
        with path.open() as fh:
            yaml.load(fh, Loader=UniqueKeyLoader)
        print(f"OK duplicate-key check: {path}")
    except Exception as exc:
        failed = True
        print(f"FAILED duplicate-key check: {path}", file=sys.stderr)
        print(exc, file=sys.stderr)

raise SystemExit(1 if failed else 0)
