#!/usr/bin/env python3
"""Check extracted pg_resetwal parsers and control assignments with fixtures.

No cluster files are read or changed. Full utility/TAP testing awaits the
complete xid64 series and its headers.
"""
from pathlib import Path
import os
import shlex
import subprocess
import sys
import tempfile

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
source = (root / "src/bin/pg_resetwal/pg_resetwal.c").read_text()


def function(signature):
    start = source.index(signature)
    opening = source.index("{", start)
    end, depth = opening + 1, 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end] + "\n"


parsers = function("static uint32\nstrtouint32_strict(")
parsers += function("static uint64\nstrtouint64_strict(")
options = source[source.index("\t\t\tcase 'D':"):
                 source.index("\t\t\tcase 'l':")]
assignment_start = source.index("\tif (oldest_xid_given)")
assignments = source[assignment_start:source.index("\tif (minXlogTli", assignment_start)]
assert "epoch" not in source.lower()
fixture = Path(__file__).with_name("fixture.c").read_text()
for marker, replacement in [("/* PARSERS */", parsers),
                            ("/* OPTION CASES */", options),
                            ("/* CONTROL ASSIGNMENTS */", assignments)]:
    assert fixture.count(marker) == 1
    fixture = fixture.replace(marker, replacement)

with tempfile.TemporaryDirectory(prefix="xid64-resetwal-") as tmp:
    tmp = Path(tmp)
    code = tmp / "check.c"
    code.write_text(fixture)
    exe = tmp / "check"
    subprocess.run(shlex.split(os.environ.get("CC", "cc")) +
                   ["-std=c11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=undefined", "-fno-sanitize-recover=all",
                    str(code), "-o", str(exe)], check=True)
    count = 0

    def check(option, value, expected=None):
        global count
        result = subprocess.run([str(exe), option, value], text=True,
                                capture_output=True)
        if expected is None:
            assert result.returncode == 1, (option, value, result)
            assert "runtime error" not in result.stderr, result.stderr
        else:
            assert result.returncode == 0, (option, value, result)
            values = dict(item.split("=") for item in result.stdout.split())
            for field, number in expected.items():
                assert int(values[field]) == number, (option, value, values)
        count += 1

    maximum = 2**64 - 1
    for option, field in [("x", "xid"), ("u", "oldest")]:
        for number in [3, 2**32 - 1, 2**32, 10**10, 2**63, maximum]:
            check(option, str(number), {field: number})
        for value in ["", "foo", "3x", "0", "1", "2", "-1", " -100", str(2**64)]:
            check(option, value)
    check("c", "4294967296,10000000000", {"cts_old": 2**32, "cts_new": 10**10})
    check("c", "0,0", {"cts_old": 0, "cts_new": 0})
    check("c", f"{maximum},{maximum}", {"cts_old": maximum, "cts_new": maximum})
    for value in ["-1,3", "3,-1", "1,3", "3,1", "3,", ",3", "3,foo", f"3,{2**64}"]:
        check("c", value)
    check("m", "4294967296,10000000000", {"multi": 2**32, "old_multi": 10**10})
    check("m", f"{maximum},{maximum}", {"multi": maximum, "old_multi": maximum})
    for value in ["0,1", "1,0", "-1,1", "1,-1", f"{2**64},1", "1,foo"]:
        check("m", value)
    for number in [1, 2**32, maximum]:
        check("O", str(number), {"offset": number})
    for value in ["0", "-1", str(2**64), "foo"]:
        check("O", value)
    check("o", str(2**32 - 1), {"oid": 2**32 - 1})
    for value in ["0", "-1", str(2**32), "foo"]:
        check("o", value)
    print(f"PASS: {count} pg_resetwal parser/control cases; high XIDs, OID bounds, "
          "explicit zero commit-ts reset, offset rules, invalid inputs; UBSan enabled.")
