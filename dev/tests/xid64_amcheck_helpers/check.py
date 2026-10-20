#!/usr/bin/env python3
"""Exercise actual corruption-test helpers without starting a PostgreSQL server."""
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
source = (root / "src/bin/pg_amcheck/t/004_verify_heapam.pl").read_text()
helpers = source[source.index("use constant HEAPTUPLE_PACK_CODE"):
                 source.index("# Set umask")]
fixture = Path(__file__).with_name("fixture.pl").read_text()
assert fixture.count("# PRODUCTION HELPERS") == 1
with tempfile.TemporaryDirectory(prefix="xid64-amcheck-helpers-") as tmp:
    probe = Path(tmp) / "check.pl"
    probe.write_text(fixture.replace("# PRODUCTION HELPERS", helpers))
    subprocess.run(["perl", str(probe)], check=True)
