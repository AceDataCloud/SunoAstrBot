"""Refresh the reviewed Suno model list and its runtime/tool description."""

import argparse
import json
import re
from datetime import date
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts/suno-models.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--refresh", action="store_true", help="Read the public contract only"
    )
    group.add_argument(
        "--check", action="store_true", help="Check generated output offline"
    )
    args = parser.parse_args()
    contract = json.loads(CONTRACT.read_text())
    if args.refresh:
        with urlopen(contract["source"], timeout=30) as response:
            api = json.load(response)
        schema = api["definition"]["paths"][contract["path"]]["post"]["requestBody"][
            "content"
        ]["application/json"]["schema"]
        contract["models"] = schema["properties"]["model"]["enum"]
        contract["captured_at"] = date.today().isoformat()
        CONTRACT.write_text(json.dumps(contract, indent=2) + "\n")
    models = contract["models"]
    if (
        not models
        or len(models) != len(set(models))
        or not all(isinstance(m, str) and m for m in models)
    ):
        raise ValueError("Invalid Suno model list")
    block = (
        "# BEGIN GENERATED SUNO MODELS\nMODELS = {\n"
        + "".join("    " + json.dumps(m) + ",\n" for m in models)
        + "}\n# END GENERATED SUNO MODELS"
    )
    client = ROOT / "client.py"
    client_text, count = re.subn(
        r"# BEGIN GENERATED SUNO MODELS.*?# END GENERATED SUNO MODELS",
        block,
        client.read_text(),
        flags=re.DOTALL,
    )
    if count != 1:
        raise ValueError("Expected exactly one generated model block")
    tool = ROOT / "main.py"
    description = "            model(string): " + ", ".join(models) + "."
    tool_text, count = re.subn(
        r"^            model\(string\):.*$",
        description,
        tool.read_text(),
        flags=re.MULTILINE,
    )
    if count != 1:
        raise ValueError("Expected exactly one model argument description")
    for path, content in [(client, client_text), (tool, tool_text)]:
        if args.check:
            if path.read_text() != content:
                raise SystemExit(f"Stale model projection: {path.name}")
        else:
            path.write_text(content)


if __name__ == "__main__":
    main()
