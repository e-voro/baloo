#!/usr/bin/env python3
"""Exercise production page conversion/hint code during the partial xid64 port.

Uses the real bufpage.h and extracted C functions, with fixed-width tuple and
backend-service fixtures. This is not a server, concurrency, or WAL replay test.
Future tuple helpers are obtained by applying their minis to original blobs.
"""
from pathlib import Path
import os
import re
import shlex
import subprocess
import tempfile

root = Path(__file__).resolve().parents[4]
here = Path(__file__).resolve().parent


def read(path):
    return (root / path).read_text()


def function(source, signature):
    start = source.index(signature)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end] + "\n"


with tempfile.TemporaryDirectory(prefix="xid64-page-conversion-") as tmp:
    work = Path(tmp)

    def future(number):
        patch = read("baloo/dev/cache/patches/mini/v1900-0005-Use-64-bit-XIDs/"
                     f"mini{number}-v1900-0005-Use-64-bit-XIDs.patch")
        name = re.search(r"^--- a/(.+)$", patch, re.M).group(1)
        blob = re.search(r"^index ([0-9a-f]+)\.\.", patch, re.M).group(1)
        target = work / number / name
        target.parent.mkdir(parents=True)
        target.write_bytes(subprocess.check_output(["git", "show", blob], cwd=root))
        subprocess.run(["git", "apply", "-"], input=patch, text=True,
                       cwd=work / number, check=True)
        return target.read_text()

    # Use real page/header definitions; only their external dependencies stubbed.
    for path in ("access/transam.h", "access/multixact.h", "access/xlogdefs.h",
                 "utils/elog.h"):
        target = work / "include" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("/* Definitions supplied by fixture.c. */\n")

    htup = future("0140")
    heapam = read("src/include/access/heapam.h")
    source = read("src/backend/storage/page/bufpage.c")
    production = source[source.index("static HeapPageSpecialData"):
                        source.index("/* ----------------------------------------------------------------")]
    production += function(read("src/backend/storage/buffer/heap_convert.c"),
                           "int\nitemoffcompare(")
    for name in ("HeapTupleHeaderGetDoubleXmax", "HeapTupleHeaderSetDoubleXmax",
                 "HeapTupleSetXmax", "HeapTupleHeaderStoreXmax"):
        start = htup.rfind("static inline", 0, htup.index(name + "("))
        production += function(htup, htup[start:htup.index("(", start) + 1])
    for name in ("heap_execute_freeze_tuple", "heap_execute_freeze_tuple_page"):
        production += function(heapam, "static inline void\n" + name + "(")
    for name in ("heap_page_double_xmax_get_min_max", "heap_page_add_special_area",
                 "compactify_tuples"):
        production += function(source, "static void\n" + name + "(")
    production += function(source, "void\nPageRepairFragmentation(")
    production += function(read("src/backend/access/heap/heapam.c"),
                           "static void\nheap_page_shift_base(")

    # Ensure the executable sequence below matches both production call orders.
    primary = read("src/backend/access/heap/pruneheap.c")
    primary = primary[primary.index("\nheap_page_prune_and_freeze("):]
    redo = read("src/backend/access/heap/heapam_xlog.c")
    redo = function(redo, "static void\nheap_xlog_prune_freeze(")
    assert primary.index("heap_freeze_prepared_tuples(") < primary.index("heap_page_prune_execute(")
    assert redo.index("heap_execute_freeze_tuple_page(") < redo.index("heap_page_prune_execute(")

    fixture = (here / "fixture.c").read_text()
    generated = work / "check.c"
    generated.write_text(fixture.replace("/* PRODUCTION */", production))
    compiler = shlex.split(os.environ.get("CC", "cc"))
    for size in (1024, 2048, 4096, 8192, 16384, 32768):
        binary = work / "check"
        subprocess.run(compiler + ["-std=c11", "-O1", "-g", "-Wall", "-Wextra",
                       "-Werror", "-Wno-unused-parameter", "-Wno-sign-compare",
                       "-fsanitize=undefined",
                       "-fno-sanitize-recover=all", f"-DBLCKSZ={size}",
                       "-I" + str(work / "include"), "-I" + str(root / "src/include"),
                       str(generated), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
