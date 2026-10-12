#!/usr/bin/env python3
"""lockfile-audit-diff: audit diff between two dependency lockfiles.

Supports pip-freeze style TXT (name==version) and a canonical JSON package
list. Produces added/removed/changed sets plus risk annotations for newly
added dependencies (license unknown, pre-1.0 version, typosquat name
proximity, unparseable version, deep transitive placement). Pure stdlib.
"""
import argparse
import json
import sys
from collections import deque


# ---------------- parsing ----------------

def parse_txt(text):
    pkgs = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        if "==" not in line:
            continue
        name, _, version = line.partition("==")
        name, version = name.strip(), version.strip()
        if not name or not version:
            continue
        pkgs[name] = {"version": version, "license": None, "dependencies": []}
    return pkgs


def parse_json_doc(doc):
    if isinstance(doc, list):
        doc = {"packages": doc}
    if not isinstance(doc, dict) or not isinstance(doc.get("packages"), list):
        raise ValueError("JSON lockfile must contain a 'packages' list")
    pkgs = {}
    for i, p in enumerate(doc["packages"]):
        if not isinstance(p, dict) or not p.get("name"):
            raise ValueError("packages[%d]: missing 'name'" % i)
        deps = p.get("dependencies") or []
        if not isinstance(deps, list):
            raise ValueError("packages[%d]: 'dependencies' must be a list" % i)
        pkgs[str(p["name"])] = {"version": str(p.get("version", "")),
                                "license": p.get("license"),
                                "dependencies": [str(d) for d in deps]}
    return pkgs


def load_lockfile(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError("invalid JSON lockfile: %s" % e)
        return parse_json_doc(doc)
    return parse_txt(text)


# ---------------- graph ----------------

def compute_depths(pkgs):
    """Shortest distance from roots (packages nobody depends on).
    Cycle members and orphans unreachable from roots get depth -1."""
    depended = set()
    for p in pkgs.values():
        for d in p.get("dependencies", []):
            depended.add(d)
    depth = {}
    queue = deque((n, 0) for n in pkgs if n not in depended)
    seen = {n for n, _ in queue}
    while queue:
        name, d = queue.popleft()
        depth[name] = d
        for dep in pkgs[name].get("dependencies", []):
            if dep in pkgs and dep not in seen:
                seen.add(dep)
                queue.append((dep, d + 1))
    for n in pkgs:
        depth.setdefault(n, -1)
    return depth


def levenshtein(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1,
                         prev[j - 1] + (a[i - 1] != b[j - 1]))
        prev = cur
    return prev[-1]


# ---------------- diff + risk ----------------

RISK_DESCRIPTIONS = {
    "license-unknown": "added package declares no license field",
    "pre-1.0": "added package version is pre-1.0 (0.y.z)",
    "typosquat-proximity": "added name within edit distance 2 of an existing dependency",
    "unparseable-version": "version does not look like x.y.z",
    "deep-transitive": "added package sits at dependency depth >= 4",
}


def _version_bits(version):
    parts = version.split(".")
    if not parts or not all(p.isdigit() for p in parts[:3]) or len(parts) < 2:
        return None
    return [int(p) for p in parts[:3]]


def annotate_risks(added, old_pkgs, depths):
    out = {}
    existing = [n.lower() for n in old_pkgs if n.lower() != ""]
    for name, info in sorted(added.items()):
        risks = []
        if not info.get("license"):
            risks.append("license-unknown")
        bits = _version_bits(info.get("version", ""))
        if bits is None:
            risks.append("unparseable-version")
        elif bits[0] == 0:
            risks.append("pre-1.0")
        if depths.get(name, -1) >= 4:
            risks.append("deep-transitive")
        low = name.lower()
        for ex in existing:
            if ex == low:
                continue
            if abs(len(ex) - len(low)) <= 2 and levenshtein(ex, low) <= 2:
                risks.append("typosquat-proximity")
                break
        out[name] = risks
    return out


def diff_locks(old, new):
    added = {n: new[n] for n in new if n not in old}
    removed = sorted(n for n in old if n not in new)
    changed = {n: {"from": old[n]["version"], "to": new[n]["version"]}
               for n in new if n in old and old[n]["version"] != new[n]["version"]}
    unchanged = sum(1 for n in new if n in old and old[n]["version"] == new[n]["version"])
    depths = compute_depths({**old, **new})
    risks = annotate_risks(added, old, depths)
    return {"added": sorted(added), "removed": removed, "changed": changed,
            "unchanged_count": unchanged, "risk_annotations": risks,
            "risk_descriptions": RISK_DESCRIPTIONS,
            "clean": not risks}


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="lockfile-audit-diff",
        description="Diff two lockfiles and risk-annotate added dependencies.")
    parser.add_argument("old", help="old lockfile (TXT or JSON)")
    parser.add_argument("new", help="new lockfile (TXT or JSON)")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    parser.add_argument("--exit-zero", action="store_true")
    args = parser.parse_args(argv)

    try:
        old = load_lockfile(args.old)
        new = load_lockfile(args.new)
    except (OSError, ValueError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    report = diff_locks(old, new)
    if args.format == "text":
        print("added: %s" % ", ".join(report["added"]) or "(none)")
        print("removed: %s" % ", ".join(report["removed"]) or "(none)")
        for n, r in sorted(report["changed"].items()):
            print("changed: %s %s -> %s" % (n, r["from"], r["to"]))
        for n, risks in sorted(report["risk_annotations"].items()):
            if risks:
                print("risk: %s [%s]" % (n, ",".join(risks)))
        print("clean: %s" % report["clean"])
    else:
        print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    if args.exit_zero:
        return 0
    return 1 if report["risk_annotations"] else 0


if __name__ == "__main__":
    sys.exit(main())
