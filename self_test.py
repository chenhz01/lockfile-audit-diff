#!/usr/bin/env python3
"""Self-tests for lockfile-audit-diff. Run: python self_test.py"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core

CASES = []


def case(fn):
    CASES.append(fn)
    return fn


def expect(cond, msg="assertion failed"):
    if not cond:
        raise AssertionError(msg)


def expect_raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return
    raise AssertionError("expected %s to be raised" % exc.__name__)


def pkg(name, version="1.0.0", license="MIT", deps=None):
    return {"name": name, "version": version, "license": license,
            "dependencies": deps or []}


def doc(*packages):
    return {"packages": list(packages)}


# ---------- functional: parsers ----------

@case
def t_txt_basic():
    pkgs = core.parse_txt("requests==2.31.0\nflask==3.0.0\n")
    expect(set(pkgs) == {"requests", "flask"}, "got %r" % pkgs)


@case
def t_txt_comments_and_blanks():
    pkgs = core.parse_txt("# header\n\nrequests==2.31.0\n\n# tail\n")
    expect(set(pkgs) == {"requests"}, "got %r" % pkgs)


@case
def t_txt_spaces_around_eq():
    pkgs = core.parse_txt("requests == 2.31.0\n")
    expect(pkgs["requests"]["version"] == "2.31.0", "spaces not handled")


@case
def t_txt_malformed_lines_skipped():
    pkgs = core.parse_txt("requests==2.31.0\nnot-a-pin\n-e extras\n")
    expect(set(pkgs) == {"requests"}, "got %r" % pkgs)


@case
def t_txt_unicode_name():
    pkgs = core.parse_txt("pïpj==1.0.0\n")
    expect("pïpj" in pkgs, "unicode name lost")


@case
def t_txt_duplicate_last_wins():
    pkgs = core.parse_txt("a==1.0.0\na==2.0.0\n")
    expect(pkgs["a"]["version"] == "2.0.0", "dup handling wrong")


@case
def t_json_basic():
    pkgs = core.parse_json_doc(doc(pkg("a"), pkg("b", deps=["a"])))
    expect(pkgs["b"]["dependencies"] == ["a"], "deps lost")


@case
def t_json_list_form():
    pkgs = core.parse_json_doc([pkg("a")])
    expect("a" in pkgs, "list form must be accepted")


@case
def t_json_missing_name_raises():
    expect_raises(ValueError, core.parse_json_doc, {"packages": [{"v": "1"}]})


@case
def t_json_missing_packages_raises():
    expect_raises(ValueError, core.parse_json_doc, {"nope": []})


@case
def t_json_bad_deps_raises():
    expect_raises(ValueError, core.parse_json_doc,
                  {"packages": [{"name": "a", "dependencies": "x"}]})


@case
def t_json_license_null():
    pkgs = core.parse_json_doc(doc(pkg("a", license=None)))
    expect(pkgs["a"]["license"] is None, "license null lost")


@case
def t_json_empty_packages():
    expect(core.parse_json_doc({"packages": []}) == {}, "empty expected")


@case
def t_loader_sniffs_json():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "lock.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(doc(pkg("a")), f)
    expect("a" in core.load_lockfile(p), "json sniff failed")


@case
def t_loader_sniffs_txt():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "lock.txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write("a==1.0.0\n")
    expect("a" in core.load_lockfile(p), "txt default failed")


@case
def t_loader_invalid_json_raises():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "lock.json")
    with open(p, "w", encoding="utf-8") as f:
        f.write("{broken")
    expect_raises(ValueError, core.load_lockfile, p)


# ---------- functional: diff ----------

@case
def t_diff_added_removed_changed():
    old = core.parse_json_doc(doc(pkg("a"), pkg("b", "1.0.0"), pkg("c")))
    new = core.parse_json_doc(doc(pkg("a"), pkg("b", "2.0.0"), pkg("d")))
    r = core.diff_locks(old, new)
    expect(r["added"] == ["d"] and r["removed"] == ["c"], "sets: %r" % r)
    expect(r["changed"] == {"b": {"from": "1.0.0", "to": "2.0.0"}},
           "changed: %r" % r["changed"])
    expect(r["unchanged_count"] == 1, "unchanged: %r" % r["unchanged_count"])


@case
def t_diff_both_empty():
    r = core.diff_locks({}, {})
    expect(r["added"] == [] and r["clean"] is True, "empty diff not clean")


@case
def t_diff_identical():
    same = core.parse_json_doc(doc(pkg("a")))
    r = core.diff_locks(same, core.parse_json_doc(doc(pkg("a"))))
    expect(r["added"] == [] and r["changed"] == {}, "identical must be quiet")


# ---------- functional: depths ----------

@case
def t_depth_chain():
    pkgs = core.parse_json_doc(
        doc(pkg("top", deps=["mid"]), pkg("mid", deps=["leaf"]), pkg("leaf")))
    d = core.compute_depths(pkgs)
    expect((d["top"], d["mid"], d["leaf"]) == (0, 1, 2), "depths: %r" % d)


@case
def t_depth_cycle_safe():
    pkgs = core.parse_json_doc(
        doc(pkg("a", deps=["b"]), pkg("b", deps=["a"])))
    d = core.compute_depths(pkgs)
    expect(d["a"] == -1 and d["b"] == -1, "cycle must terminate: %r" % d)


@case
def t_depth_multiple_roots():
    pkgs = core.parse_json_doc(doc(pkg("r1", deps=["l"]), pkg("r2"), pkg("l")))
    d = core.compute_depths(pkgs)
    expect(d["r1"] == 0 and d["r2"] == 0 and d["l"] == 1, "roots: %r" % d)


@case
def t_depth_missing_dep_ignored():
    pkgs = core.parse_json_doc(doc(pkg("a", deps=["ghost"])))
    d = core.compute_depths(pkgs)
    expect(d["a"] == 0, "ghost dep must not crash: %r" % d)


@case
def t_depth_long_chain_50():
    names = ["n%02d" % i for i in range(50)]
    packages = [pkg(names[i], deps=[names[i + 1]]) for i in range(49)]
    packages.append(pkg(names[49]))
    d = core.compute_depths(core.parse_json_doc(doc(*packages)))
    expect(d["n49"] == 49, "deep chain: %r" % d["n49"])


# ---------- functional: levenshtein + risks ----------

@case
def t_levenshtein_basics():
    expect(core.levenshtein("", "") == 0, "empty")
    expect(core.levenshtein("a", "") == 1, "insert")
    expect(core.levenshtein("kitten", "sitting") == 3, "classic")
    expect(core.levenshtein("abc", "abc") == 0, "equal")


@case
def t_risk_license_unknown():
    r = core.annotate_risks({"x": {"version": "1.0.0", "license": None,
                                   "dependencies": []}}, {}, {"x": 0})
    expect(r["x"] == ["license-unknown"], "got %r" % r)


@case
def t_risk_license_present_ok():
    r = core.annotate_risks({"x": {"version": "1.0.0", "license": "MIT",
                                   "dependencies": []}}, {}, {"x": 0})
    expect(r["x"] == [], "got %r" % r)


@case
def t_risk_pre_1_0():
    r = core.annotate_risks({"x": {"version": "0.9.1", "license": "MIT",
                                   "dependencies": []}}, {}, {"x": 0})
    expect("pre-1.0" in r["x"], "got %r" % r)


@case
def t_risk_unparseable_version():
    r = core.annotate_risks({"x": {"version": "abc", "license": "MIT",
                                   "dependencies": []}}, {}, {"x": 0})
    expect("unparseable-version" in r["x"], "got %r" % r)


@case
def t_risk_two_part_version_ok():
    r = core.annotate_risks({"x": {"version": "1.0", "license": "MIT",
                                   "dependencies": []}}, {}, {"x": 0})
    expect(r["x"] == [], "two-part version should parse")


@case
def t_risk_typosquat():
    old = core.parse_json_doc(doc(pkg("requests")))
    added = {"reqeusts": {"version": "1.0.0", "license": "MIT",
                          "dependencies": []}}
    r = core.annotate_risks(added, old, {"reqeusts": 0})
    expect("typosquat-proximity" in r["reqeusts"], "got %r" % r)


@case
def t_risk_no_typosquat_for_unrelated():
    old = core.parse_json_doc(doc(pkg("requests")))
    added = {"zebra-lib": {"version": "1.0.0", "license": "MIT",
                           "dependencies": []}}
    r = core.annotate_risks(added, old, {"zebra-lib": 0})
    expect(r["zebra-lib"] == [], "got %r" % r)


@case
def t_risk_deep_transitive():
    added = {"deep": {"version": "1.0.0", "license": "MIT",
                      "dependencies": []}}
    r = core.annotate_risks(added, {}, {"deep": 4})
    expect("deep-transitive" in r["deep"], "got %r" % r)


@case
def t_risk_added_sorted_deterministic():
    added = {"b": {"version": "0.1.0", "license": None, "dependencies": []},
             "a": {"version": "0.1.0", "license": None, "dependencies": []}}
    r1 = core.annotate_risks(added, {}, {})
    r2 = core.annotate_risks(added, {}, {})
    expect(list(r1) == list(r2) == ["a", "b"], "order: %r" % list(r1))


@case
def t_risk_same_name_not_typosquat():
    old = core.parse_json_doc(doc(pkg("samepkg")))
    added = {"samepkg": {"version": "2.0.0", "license": "MIT",
                         "dependencies": []}}
    r = core.annotate_risks(added, old, {"samepkg": 0})
    expect("typosquat-proximity" not in r["samepkg"], "self-match bug")


# ---------- CLI ----------

def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


@case
def t_cli_risks_exit_one():
    d = tempfile.mkdtemp()
    o = _write(os.path.join(d, "old.json"), json.dumps(doc(pkg("a"))))
    n = _write(os.path.join(d, "new.json"), json.dumps(doc(pkg("b"))))
    expect(core.main([o, n]) == 1, "unlicensed addition must exit 1")


@case
def t_cli_clean_exit_zero():
    d = tempfile.mkdtemp()
    o = _write(os.path.join(d, "old.json"), json.dumps(doc(pkg("a", license="MIT"))))
    n = _write(os.path.join(d, "new.json"), json.dumps(doc(pkg("a", license="MIT"))))
    expect(core.main([o, n]) == 0, "clean must exit 0")


@case
def t_cli_missing_file_exit_two():
    expect(core.main(["Z:/a.json", "Z:/b.json"]) == 2, "missing exits 2")


@case
def t_cli_malformed_exit_two():
    d = tempfile.mkdtemp()
    bad = _write(os.path.join(d, "bad.json"), "{nope")
    ok = _write(os.path.join(d, "ok.json"), json.dumps(doc(pkg("a"))))
    expect(core.main([bad, ok]) == 2, "malformed exits 2")


@case
def t_cli_txt_inputs():
    d = tempfile.mkdtemp()
    o = _write(os.path.join(d, "old.txt"), "a==1.0.0\n")
    n = _write(os.path.join(d, "new.txt"), "a==1.0.0\nb==0.1.0\n")
    expect(core.main([o, n]) == 1, "txt diff with risk must exit 1")


@case
def t_cli_text_format_runs():
    d = tempfile.mkdtemp()
    o = _write(os.path.join(d, "old.txt"), "a==1.0.0\n")
    n = _write(os.path.join(d, "new.txt"), "a==2.0.0\n")
    expect(core.main([o, n, "--format", "text"]) == 0, "text runs")


@case
def t_cli_exit_zero_flag():
    d = tempfile.mkdtemp()
    o = _write(os.path.join(d, "old.json"), json.dumps(doc(pkg("a"))))
    n = _write(os.path.join(d, "new.json"), json.dumps(doc(pkg("b"))))
    expect(core.main([o, n, "--exit-zero"]) == 0, "exit-zero wins")


@case
def t_large_lockfile_500():
    packages = [pkg("lib%03d" % i) for i in range(500)]
    same = core.parse_json_doc(doc(*packages))
    r = core.diff_locks(same, core.parse_json_doc(doc(*packages)))
    expect(r["unchanged_count"] == 500, "bulk diff failed")


@case
def t_report_json_serializable():
    r = core.diff_locks({}, {"a": {"version": "1.0.0", "license": None,
                                   "dependencies": []}})
    s = json.dumps(r, ensure_ascii=True, sort_keys=True)
    expect("risk_annotations" in s, "serialization failed")


def run():
    ok = 0
    for i, fn in enumerate(CASES, 1):
        try:
            fn()
            ok += 1
        except Exception as e:
            print("FAIL %02d %s: %s: %s" % (i, fn.__name__,
                                            type(e).__name__, e))
    total = len(CASES)
    print("SUMMARY: %s %d/%d" % ("PASS" if ok == total else "FAIL", ok, total))
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(run())
