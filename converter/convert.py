from pathlib import Path
import subprocess
import shutil
import hashlib


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "source"

BLACKMATRIX = SOURCE / "blackmatrix7"
V2FLY = SOURCE / "domain-list-community"

DATA = ROOT / "data"
DIST = ROOT / "dist"


BLACKMATRIX_REPO = (
    "https://github.com/blackmatrix7/ios_rule_script.git"
)

V2FLY_REPO = (
    "https://github.com/v2fly/domain-list-community.git"
)


CONFIG = ROOT / "config"
RULES_FILE = CONFIG / "rules.txt"


def load_mapping():
    """从 config/rules.txt 读取 源目录 -> geosite分类名 映射。"""
    mapping = {}

    with RULES_FILE.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()

            if not line or line.startswith("#"):
                continue

            source, sep, name = line.partition(":")
            source = source.strip()
            name = name.strip()

            if not sep or not source or not name:
                continue

            mapping[source] = name

    if not mapping:
        raise RuntimeError(f"未找到有效映射: {RULES_FILE}")

    return mapping


def run(cmd, cwd=None):
    print("+", " ".join(str(x) for x in cmd))

    subprocess.run(
        cmd,
        cwd=cwd,
        check=True
    )


def clone_or_update(repo, path):
    if path.exists() and (path / ".git").exists():
        print(f"Updating {path}")

        run(
            ["git", "fetch", "--depth=1", "origin"],
            cwd=path
        )

        run(
            ["git", "reset", "--hard", "origin/master"],
            cwd=path
        )

    else:
        if path.exists():
            shutil.rmtree(path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        run(
            [
                "git",
                "clone",
                "--depth=1",
                repo,
                str(path)
            ]
        )


def clean_generated_data():
    DATA.mkdir(
        parents=True,
        exist_ok=True
    )

    for file in DATA.iterdir():
        if file.is_file():
            file.unlink()


def parse_rule_file(path):
    rules = set()

    with path.open(
        "r",
        encoding="utf-8"
    ) as f:

        for raw in f:
            line = raw.strip()

            if not line.startswith("- "):
                continue

            line = line[2:].strip()

            parts = line.split(",", 2)

            if len(parts) < 2:
                continue

            rule_type = parts[0].strip()
            value = parts[1].strip()

            if not value:
                continue

            if rule_type == "DOMAIN":
                rules.add(f"full:{value}")

            elif rule_type == "DOMAIN-SUFFIX":
                rules.add(f"domain:{value}")

    return rules


def convert_rule(folder, output_name):
    clash_root = (
        BLACKMATRIX
        / "rule"
        / "Clash"
    )

    rule_dir = clash_root / folder

    print()
    print("=" * 60)
    print(f"Converting: {folder}")
    print(f"Source: {rule_dir}")
    print("=" * 60)

    if not rule_dir.exists():
        print("Available directories:")

        if clash_root.exists():
            for item in sorted(clash_root.iterdir()):
                if item.is_dir():
                    print("  ", item.name)

        raise RuntimeError(
            f"BlackMatrix7 rule not found: {folder}"
        )

    rules = set()

    yaml_files = list(
        rule_dir.rglob("*.yaml")
    )

    if not yaml_files:
        raise RuntimeError(
            f"No YAML files found in: {rule_dir}"
        )

    print(
        f"Found {len(yaml_files)} YAML files"
    )

    for path in yaml_files:

        print(
            f"Reading: {path.relative_to(rule_dir)}"
        )

        rules.update(
            parse_rule_file(path)
        )

    output = DATA / output_name

    with output.open(
        "w",
        encoding="utf-8"
    ) as f:

        for rule in sorted(rules):
            f.write(rule + "\n")

    print(
        f"Generated {output}"
    )

    print(
        f"Rules: {len(rules)}"
    )


def write_private():
    source = CONFIG / "private.txt"
    output = DATA / "private"

    known_prefixes = ("full:", "domain:", "keyword:", "regexp:")

    rules = []

    with source.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()

            if not line or line.startswith("#"):
                continue

            # 裸域名默认按 DOMAIN-SUFFIX(后缀匹配) 处理，自动补 domain: 前缀
            if not line.startswith(known_prefixes):
                line = f"domain:{line}"

            rules.append(line)

    output.write_text(
        "\n".join(rules) + "\n",
        encoding="utf-8"
    )

    print()
    print("Generated custom private:")
    print(f"  {source} -> {output}")
    print(f"  {len(rules)} rule(s)")


def build_geosite():
    DIST.mkdir(
        parents=True,
        exist_ok=True
    )

    output = DIST / "geosite.dat"

    run(
        [
            "go",
            "run",
            "./",
            f"--datapath={DATA}",
            f"--outputdir={DIST}",
            "--outputname=geosite.dat",
        ],
        cwd=V2FLY
    )

    if not output.exists():
        raise RuntimeError(
            "geosite.dat was not generated"
        )

    sha256 = hashlib.sha256()

    with output.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b""
        ):
            sha256.update(chunk)

    checksum = (
        DIST
        / "geosite.dat.sha256"
    )

    checksum.write_text(
        f"{sha256.hexdigest()}  geosite.dat\n",
        encoding="utf-8"
    )

    print()
    print("Build complete:")
    print(f"  {output}")
    print(f"  {checksum}")
    print(
        f"Size: {output.stat().st_size / 1024:.1f} KiB"
    )


def build():

    print("Preparing source repositories...")

    SOURCE.mkdir(
        parents=True,
        exist_ok=True
    )

    clone_or_update(
        BLACKMATRIX_REPO,
        BLACKMATRIX
    )

    clone_or_update(
        V2FLY_REPO,
        V2FLY
    )

    clean_generated_data()

    mapping = load_mapping()

    print(f"Loaded {len(mapping)} mapping(s) from {RULES_FILE}")

    for folder, output_name in mapping.items():
        convert_rule(
            folder,
            output_name
        )

    write_private()

    build_geosite()


if __name__ == "__main__":
    build()