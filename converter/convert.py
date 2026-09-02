import os
import re
import shutil
import subprocess
from pathlib import Path

# BlackMatrix7 upstream
BLACKMATRIX_REPO = "https://github.com/blackmatrix7/ios_rule_script.git"

# V2Fly geosite builder
V2FLY_REPO = "https://github.com/v2fly/domain-list-community.git"

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "source"
BM7 = SOURCE / "ios_rule_script"
V2FLY = SOURCE / "domain-list-community"
DATA = ROOT / "data"
CONFIG = ROOT / "config" / "rules.txt"

# BlackMatrix7 folder -> geosite name
MAPPING = {
    "Apple": "apple",
    "Binance": "binance",
    "Google": "google",
    "Microsoft": "microsoft",
    "Steam": "steam",
    "SteamCN": "steamcn",
    "China": "cn",
}


def run(cmd, cwd=None):
    print("+", " ".join(str(x) for x in cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def clone_or_update(repo, path):
    if path.exists():
        run(["git", "fetch", "--depth=1", "origin"], cwd=path)
        run(["git", "reset", "--hard", "origin/master"], cwd=path)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        run([
            "git", "clone",
            "--depth=1",
            repo,
            str(path)
        ])


def parse_yaml_rule(line):
    """
    Convert BlackMatrix7 Clash classical rules:

    DOMAIN,example.com
        -> full:example.com

    DOMAIN-SUFFIX,example.com
        -> domain:example.com

    DOMAIN-KEYWORD,example
        -> keyword:example

    Everything else is ignored.
    """

    line = line.strip()

    if not line or line.startswith("#"):
        return None

    if not line.startswith("- "):
        return None

    line = line[2:].strip()

    parts = line.split(",")

    if len(parts) < 2:
        return None

    rule_type = parts[0].strip().upper()
    value = parts[1].strip()

    if rule_type == "DOMAIN":
        return f"full:{value.lower()}"

    if rule_type == "DOMAIN-SUFFIX":
        return f"domain:{value.lower()}"

    if rule_type == "DOMAIN-KEYWORD":
        return f"keyword:{value.lower()}"

    return None


def convert_rule(folder, output_name):
    source_folder = BM7 / "rule" / "Clash" / folder

    if not source_folder.exists():
        raise RuntimeError(
            f"BlackMatrix7 rule not found: {folder}"
        )

    rules = set()

    # Important:
    # Scan ALL yaml files, not just Folder.yaml.
    # This handles *_Domain.yaml and other split files.
    for yaml_file in sorted(source_folder.glob("*.yaml")):

        # Ignore README-like files if present
        if yaml_file.name.lower().startswith("readme"):
            continue

        print(f"Reading: {yaml_file}")

        with yaml_file.open(
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as f:

            for line in f:
                result = parse_yaml_rule(line)

                if result:
                    rules.add(result)

    if not rules:
        raise RuntimeError(
            f"No domain rules found for {folder}"
        )

    output = DATA / output_name
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8") as f:
        for rule in sorted(rules):
            f.write(rule + "\n")

    print(
        f"{folder} -> {output_name}: "
        f"{len(rules)} rules"
    )


def clean_generated_data():
    DATA.mkdir(parents=True, exist_ok=True)

    # Remove generated BlackMatrix lists.
    for name in MAPPING.values():
        path = DATA / name
        if path.exists():
            path.unlink()


def build():
    clean_generated_data()

    # Read requested rules
    requested = []

    with CONFIG.open(
        "r",
        encoding="utf-8"
    ) as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            requested.append(line)

    for folder in requested:

        if folder not in MAPPING:
            raise RuntimeError(
                f"Unknown rule in rules.txt: {folder}"
            )

        convert_rule(
            folder,
            MAPPING[folder]
        )

    # Make sure private exists.
    private = DATA / "private"

    if not private.exists():
        raise RuntimeError(
            "data/private is missing"
        )

    # Build V2Fly geosite.dat
    output_dir = ROOT / "dist"
    output_dir.mkdir(exist_ok=True)

    run(
        [
            "go",
            "run",
            "./",
            f"--datapath={DATA}",
            f"--outputdir={output_dir}",
            "--outputname=geosite.dat",
        ],
        cwd=V2FLY
    )

    # SHA256
    dat_file = output_dir / "geosite.dat"

    sha256 = subprocess.check_output(
        ["sha256sum", str(dat_file)],
        text=True
    ).split()[0]

    (output_dir / "geosite.dat.sha256").write_text(
        sha256 + "\n",
        encoding="utf-8"
    )

    print()
    print("====================================")
    print("Build completed")
    print("====================================")
    print(f"Output: {dat_file}")
    print(f"SHA256: {sha256}")


if __name__ == "__main__":
    build()
