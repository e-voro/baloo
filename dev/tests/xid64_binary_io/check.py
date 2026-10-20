#!/usr/bin/env python3
"""Check production xid binary I/O during the partial xid64 port.

Compile extracted xidrecv/xidsend and pqformat helpers with fixed-width Datum,
StringInfo, allocation and error-handling fixtures. This is not a backend test.
"""
from pathlib import Path
import os
import shlex
import subprocess
import sys
import tempfile

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()


def function(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    end, depth = opening + 1, 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end] + "\n"


xid = (root / "src/backend/utils/adt/xid.c").read_text()
pq = (root / "src/backend/libpq/pqformat.c").read_text()
pqh = (root / "src/include/libpq/pqformat.h").read_text()
code = function(pq, "void\npq_copymsgbytes(")
code += function(pq, "unsigned int\npq_getmsgint(")
for width in (8, 16, 32):
    code += function(pqh, f"static inline void\npq_writeint{width}(")
    code += function(pqh, f"static inline void\npq_sendint{width}(")
code += function(pqh, "static inline void\npq_sendint(")
code += function(pq, "void\npq_begintypsend(")
code += function(pq, "bytea *\npq_endtypsend(")
receiver = function(xid, "Datum\nxidrecv(")
code += receiver + function(xid, "Datum\nxidsend(")
# Negative control: reinstate exactly the original patch's two bad sizes.
assert receiver.count("sizeof(lo)") == receiver.count("sizeof(hi)") == 1
code += receiver.replace("xidrecv(", "xidrecv_before_fix(").replace(
    "sizeof(lo)", "sizeof(TransactionId)").replace(
    "sizeof(hi)", "sizeof(TransactionId)")

fixture = Path(__file__).with_name("fixture.c").read_text()
assert fixture.count("/* PRODUCTION FUNCTIONS */") == 1
with tempfile.TemporaryDirectory(prefix="xid64-binary-io-") as tmp:
    tmp = Path(tmp)
    source = tmp / "check.c"
    source.write_text(fixture.replace("/* PRODUCTION FUNCTIONS */", code))
    subprocess.run(shlex.split(os.environ.get("CC", "cc")) +
                   ["-std=c11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=undefined", "-fno-sanitize-recover=all",
                    str(source), "-o", str(tmp / "check")], check=True)
    subprocess.run([str(tmp / "check")], check=True)
