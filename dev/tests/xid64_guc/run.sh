#!/usr/bin/env bash
# Usage: run.sh /absolute/path/to/installed/pgsql
# Requires an assertion-enabled PostgreSQL installation with patch 0004.
set -euo pipefail
prefix=$(realpath "${1:?Specify the PostgreSQL installation prefix}")
probe_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
probe_tmp=$(mktemp -d /tmp/xid64-guc-probe.XXXXXX)
export PATH="$prefix/bin:$PATH"
export LD_LIBRARY_PATH="$prefix/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
cleanup() {
  if [[ -f "$probe_tmp/data/postmaster.pid" ]]; then
    pg_ctl -D "$probe_tmp/data" -m immediate -w stop
  fi
  echo "Probe artifacts: $probe_tmp"
}
trap cleanup EXIT
"${CC:-cc}" -shared -fPIC -Wall -Werror -I"$prefix/include/server" \
  -I"$prefix/include" "$probe_dir/probe.c" -o "$probe_tmp/probe.so"
initdb -D "$probe_tmp/data" -A trust --no-locale > "$probe_tmp/initdb.log"
pg_ctl -D "$probe_tmp/data" -l "$probe_tmp/server.log" \
  -o "-c listen_addresses='' -c unix_socket_directories='$probe_tmp' -p 65439" -w start
psql -X -h "$probe_tmp" -p 65439 -d postgres -v module="$probe_tmp/probe" \
  -f "$probe_dir/probe.sql"
