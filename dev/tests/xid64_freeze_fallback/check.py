#!/usr/bin/env python3
"""Live xid64 fallback, pin concurrency and crash-redo probe; disposable cluster.

Usage: check.py INSTALL_PREFIX
Requires a completed, installed assertion build and local socket permissions.
The private cluster is stopped on exit; files/logs remain under /tmp for review.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
import time

prefix = Path(sys.argv[1]).resolve()
bindir = prefix / 'bin'
source = Path(__file__).resolve().parent
work = Path(tempfile.mkdtemp(prefix='xid64-freeze-fallback-'))
data = work / 'data'
port = '65479'
running = False


def run(args, **kwargs):
    result = subprocess.run(list(map(str, args)), text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            **kwargs)
    if result.returncode:
        print(result.stdout, flush=True)
        result.check_returncode()
    return result.stdout


def sql(query):
    return run([bindir / 'psql', '-h', work, '-p', port, '-d', 'postgres',
                '-XAt', '-v', 'ON_ERROR_STOP=1', '-c', query]).strip()


def start(fpw):
    global running
    run([bindir / 'pg_ctl', '-D', data, '-l', work / 'server.log', '-w',
         '-o', f"-k {work} -p {port} -c listen_addresses='' "
               f'-c autovacuum=off -c wal_consistency_checking=all '
               '-c autovacuum_freeze_max_age=9223372036854775807 '
               f'-c full_page_writes={fpw}', 'start'])
    running = True


def stop(mode='fast'):
    global running
    run([bindir / 'pg_ctl', '-D', data, '-m', mode, '-w', 'stop'])
    running = False


print('Artifacts:', work, flush=True)
try:
    includedir = run([bindir / 'pg_config', '--includedir-server']).strip()
    run(['cc', '-shared', '-fPIC', '-Wall', '-Werror', '-I' + includedir,
         source / 'probe.c', '-o', work / 'probe.so'])
    run([bindir / 'initdb', '-D', data, '--no-locale', '--encoding=UTF8',
         '--auth=trust'])
    start('on')
    sql(f"""CREATE EXTENSION pageinspect;
        CREATE FUNCTION xid64_hold_pin(regclass,text) RETURNS bool
        AS '{work / 'probe.so'}' LANGUAGE C STRICT;
        CREATE FUNCTION xid64_vm_status(regclass) RETURNS int
        AS '{work / 'probe.so'}' LANGUAGE C STRICT;
        CREATE FUNCTION xid64_mask_image(bytea) RETURNS bytea
        AS '{work / 'probe.so'}' LANGUAGE C STRICT;
        CREATE FUNCTION xid64_prune_no_repair(regclass) RETURNS bool
        AS '{work / 'probe.so'}' LANGUAGE C STRICT;""")

    for fpw, next_xid in [('on', 2**33), ('off', 2**34)]:
        table = 'fallback_' + fpw
        # Separate transactions leave a removable HOT root at offset 2.
        sql(f'CREATE TABLE {table}(id int, payload text) '
            'WITH (autovacuum_enabled=false)')
        sql(f"INSERT INTO {table} VALUES (1,'dead'),(2,'old-root')")
        sql(f"UPDATE {table} SET payload='survivor' WHERE id=2")
        sql(f'DELETE FROM {table} WHERE id=1')
        before = sql(f"SELECT lp,lp_off FROM heap_page_items("
                     f"get_raw_page('{table}',0)) ORDER BY lp")
        path = sql(f"SELECT pg_relation_filepath('{table}')")
        sql('CHECKPOINT')
        assert not (data / (path + '_vm')).exists(), 'unexpected VM fork'
        stop()
        run([bindir / 'pg_resetwal', '-x', str(next_xid), data])
        start(fpw)
        marker = work / ('pinned_' + fpw)
        holder = subprocess.Popen(
            [str(bindir / 'psql'), '-h', str(work), '-p', port,
             '-d', 'postgres', '-XAt', '-v', 'ON_ERROR_STOP=1', '-c',
             f"SELECT xid64_hold_pin('{table}','{marker}')"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 10
        while not marker.exists():
            if holder.poll() is not None or time.monotonic() > deadline:
                if holder.poll() is not None:
                    print(holder.communicate()[0], flush=True)
                raise AssertionError('pin holder did not become ready')
            time.sleep(0.02)
        # An erroneous cleanup-lock acquisition would block until the holder
        # exits. A statement timeout bounds that failure without hanging.
        result = sql(f"SET statement_timeout='3s'; INSERT INTO {table} "
                     "VALUES (3,'new') RETURNING xmin::text")
        assert str(next_xid) in result, result
        assert holder.poll() is None, 'holder released its pin too early'
        assert (data / (path + '_vm')).exists(), 'fallback did not pin VM'
        after = sql(f"SELECT lp,lp_flags,lp_off FROM heap_page_items("
                    f"get_raw_page('{table}',0)) ORDER BY lp")
        assert '2|2|3' in after, ('HOT root was not redirected', after)
        survivor_offset = before.splitlines()[2].split('|')[1]
        assert f'3|1|{survivor_offset}' in after, 'survivor tuple moved'
        assert sql(f"SELECT xid64_vm_status('{table}')") == '0'
        assert sql(f"SELECT xmin::text FROM {table} WHERE id=2") == '2'
        # Mask only orphaned storage: meaningful live bytes, page bases and
        # redirect metadata must still expose deliberate mismatches.
        dead_offset = int(before.splitlines()[1].split('|')[1])
        special = sql(f"SELECT special FROM page_header(get_raw_page('{table}',0))")
        for offset, masked_equal in [(dead_offset + 24, 't'),
                                     (int(survivor_offset) + 24, 'f'),
                                     (int(special), 'f'), (28, 'f')]:
            result = sql(f"SELECT xid64_mask_image(p) = xid64_mask_image("
                         f"set_byte(p,{offset},get_byte(p,{offset}) # 1)) "
                         f"FROM (SELECT get_raw_page('{table}',0) p) s")
            assert result == masked_equal, (offset, result, masked_equal)
        output, _ = holder.communicate(timeout=12)
        assert holder.returncode == 0 and output.strip() == 't', output
        expected = sql(f'SELECT id,payload FROM {table} ORDER BY id')
        assert expected == '2|survivor\n3|new', expected
        # Replay the logged no-defragmentation prune under native cleanup
        # locking. wal_consistency_checking=all also verifies heap images.
        stop('immediate')
        start(fpw)
        assert sql(f'SELECT id,payload FROM {table} ORDER BY id') == expected
        assert sql(f"SELECT lp,lp_flags,lp_off FROM heap_page_items("
                   f"get_raw_page('{table}',0)) ORDER BY lp") == after
        print(f'PASS: FPW={fpw}: fallback, concurrent pin, HOT redirect, '
              'stable tuple address/payload, frozen xmin, VM pin and crash redo',
              flush=True)
    sql('CREATE TABLE init_guard(id int) WITH (autovacuum_enabled=false)')
    sql('INSERT INTO init_guard VALUES (1)')
    sql('DELETE FROM init_guard')
    assert sql("SELECT xid64_prune_no_repair('init_guard')") == 't'
    sql('CHECKPOINT')
    assert sql('INSERT INTO init_guard VALUES (2) RETURNING ctid').splitlines()[0] == '(0,1)'
    layout = sql("SELECT lp,lp_off FROM heap_page_items(get_raw_page('init_guard',0))")
    stop('immediate')
    start('off')
    assert sql('TABLE init_guard') == '2'
    assert sql("SELECT lp,lp_off FROM heap_page_items(get_raw_page('init_guard',0))") == layout
    print('PASS: one unused slot with retained storage, first-slot insert and crash redo', flush=True)
    print('PASS: live fallback scenarios completed', flush=True)
finally:
    if running:
        stop()
