#!/usr/bin/env python3
"""Run actual upgrade readers/writer/SLRU I/O against synthetic files, with uint64 target XIDs.

This is standalone format/dispatch validation, not a live server upgrade.
"""
from pathlib import Path
import os
import re
import shlex
import struct
import subprocess
import sys
import tempfile
root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
here = Path(__file__).resolve().parent
base = root / 'src/bin/pg_upgrade'
def stripped(path):
    return re.sub(r'^#include .*\n', '', path.read_text(), flags=re.M)
def function(source, signature):
    start = source.index(signature)
    pos = source.index('{', start)
    end, depth = pos + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'
with tempfile.TemporaryDirectory(prefix='xid64-multixact-') as tmp:
    tmp = Path(tmp)
    (tmp / 'fixture.h').write_text((here / 'fixture.h').read_text())
    (tmp / 'slru_io.h').write_text(stripped(base / 'slru_io.h'))
    (tmp / 'multixact_read_v18.h').write_text('#include "slru_io.h"\n' + stripped(base / 'multixact_read_v18.h'))
    (tmp / 'target.h').write_text(stripped(root / 'src/include/access/multixact_internal.h'))
    units = []
    for name in ['multixact_read_v18.c','multixact_rewrite.c','slru_io.c','segresize.c']:
        pre = '#include "fixture.h"\n#include "slru_io.h"\n'
        if name in ['multixact_read_v18.c','multixact_rewrite.c']:
            pre += '#include "multixact_read_v18.h"\n'
        if name == 'multixact_rewrite.c':
            pre += '#include "target.h"\n'
        dest = tmp / name
        dest.write_text(pre + stripped(base / name))
        units.append(dest)
    version = (base / 'version.c').read_text()
    helpers = '#include "fixture.h"\n' + ''.join(function(version,sig) for sig in [
        'bool\ncluster_is_xid64(', 'bool\ncluster_is_xid32(', 'bool\ncluster_has_64bit_multixact_offsets('])
    heap = (root / 'src/backend/storage/buffer/heap_convert.c').read_text()
    helpers += function(heap,'static inline MultiXactId\nfull_source_multixact(')
    helpers += 'uint64 fixture_source_id(uint64 id, uint64 base) { return full_source_multixact(id, base); }\n'
    (tmp / 'helpers.c').write_text(helpers)
    (tmp / 'driver.c').write_text((here / 'driver.c').read_text())
    exe = tmp / 'fixture'
    subprocess.run(shlex.split(os.environ.get('CC','cc')) + [
        '-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=undefined',
        '-fno-sanitize-recover=all','-I',str(tmp),*[str(u) for u in units],
        str(tmp/'helpers.c'),str(tmp/'driver.c'),'-o',str(exe)],check=True)
    integration = (here / 'sql_fixture.c').read_text()
    upgrade = (base / 'pg_upgrade.c').read_text()
    integration = integration.replace('/* FUNCTIONS */','\n'.join(function(upgrade,sig) for sig in [
        'static void\ncopy_slru_subdir(', 'static void\ncopy_xact_xlog_xid(',
        'static void\nset_frozenxids(', 'static void\nadjust_multixact_horizons(']))
    (tmp/'sql_fixture.c').write_text(integration)
    sql_exe=tmp/'sql_fixture'
    subprocess.run(shlex.split(os.environ.get('CC','cc')) + [
        '-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=undefined',
        '-fno-sanitize-recover=all','-DSQL_FIXTURE_ONLY','-I',str(tmp),*[str(u) for u in units],
        str(tmp/'helpers.c'),str(tmp/'driver.c'),str(tmp/'sql_fixture.c'),'-o',str(sql_exe)],check=True)
    count = 0
    def dirs(label):
        path = tmp / label
        old,new = path/'old',path/'new'
        for cluster in [old,new]:
            for fork in ['offsets','members']:
                (cluster/'pg_multixact'/fork).mkdir(parents=True)
        return old,new
    def page_path(folder,page,long):
        return folder / (f'{page//32:015X}' if long else f'{page//32:04X}')
    def put(folder,page,offset,data,long):
        path=page_path(folder,page,long)
        mode='r+b' if path.exists() else 'w+b'
        with path.open(mode) as f:
            f.seek((page%32)*8192+offset); f.write(data)
            if f.tell()%8192:
                f.truncate(((f.tell()+8191)//8192)*8192)
    def source_offset(old,multi,value,wide):
        per=8192//(8 if wide else 4)
        put(old/'pg_multixact/offsets',multi//per,(multi%per)*(8 if wide else 4),
            struct.pack('=Q' if wide else '=I',value),False)
    def source_member(old,offset,xid,status,wide):
        # Fixed source group: 4 flag bytes and four uint32 XIDs.
        page,slot=divmod(offset,1636); group,member=divmod(slot,4)
        put(old/'pg_multixact/members',page,group*20+member,bytes([status]),wide)
        put(old/'pg_multixact/members',page,group*20+4+member*4,struct.pack('=I',xid),wide)
    def target_offset(new,multi):
        per=1024; page,entry=divmod(multi,per)
        with page_path(new/'pg_multixact/offsets',page,True).open('rb') as f:
            f.seek((page%32)*8192+entry*8)
            return struct.unpack('=Q',f.read(8))[0]
    def target_member(new,offset):
        page,slot=divmod(offset,904); group,member=divmod(slot,8)
        with page_path(new/'pg_multixact/members',page,True).open('rb') as f:
            f.seek((page%32)*8192+group*72+member); status=f.read(1)[0]
            f.seek((page%32)*8192+group*72+8+member*8)
            return struct.unpack('=Q',f.read(8))[0],status
    def run(old,new,wide,start,end,nextoff,read=False,ok=True):
        global count
        result=subprocess.run([str(exe),'rewrite',str(old),str(new),str(int(wide)),str(start),
                               str(end),str(nextoff),'read' if read else 'write'],capture_output=True,text=True)
        assert result.returncode == (0 if ok else 1), result
        assert 'runtime error' not in result.stderr,result.stderr
        count+=1
        return tuple(map(int,result.stdout.split())) if ok else ()
    for wide in [False,True]:
        # Cross offset-page and member-page boundaries; high raw XID must zero-extend.
        old,new=dirs(f'basic-{wide}')
        start=1023 if wide else 2047
        off=(2**32+1635) if wide else 1635
        source_offset(old,start,off,wide); source_offset(old,start+1,off+2,wide)
        source_member(old,off,42,1,wide); source_member(old,off+1,0xfffffffe,5,wide)
        source_member(old,off+2,77,2,wide)
        assert run(old,new,wide,start,start+2,off+3)==(start+2,3)
        assert [target_offset(new,m) for m in range(start,start+3)]==[1,2,3]
        assert target_member(new,1)==(0xfffffffe,5) and target_member(new,2)==(77,2)
        # Raw MXID wrap must work regardless of offset width.
        old,new=dirs(f'mxid-wrap-{wide}')
        ids=[0xfffffffe,0xffffffff,1,2]; off=2**32+10 if wide else 10
        for i,m in enumerate(ids):
            source_offset(old,m,off+i,wide); source_member(old,off+i,100+i,5,wide)
        assert run(old,new,wide,ids[0],3,off+4)==(2**32+2,5)
        for i in range(5): assert target_offset(new,ids[0]+i)==i+1
        for i in range(4): assert target_member(new,i+1)==(100+i,5)
        # Native crash-hole handling: invalid entries keep the preceding boundary.
        old,new=dirs(f'holes-{wide}')
        for m,value in [(3,2),(4,3),(5,0),(6,7)]: source_offset(old,m,value,wide)
        for off,xid,status in [(2,50,5),(7,60,1),(8,61,5)]: source_member(old,off,xid,status,wide)
        assert run(old,new,wide,3,7,9)==(7,3)
        assert [target_offset(new,m) for m in range(3,8)]==[1,2,0,2,3]
        assert target_member(new,2)==(61,5)
        old,new=dirs(f'empty-{wide}')
        assert run(old,new,wide,9,9,1)==(9,1)
        assert target_offset(new,9)==0
    # Target 72-byte groups and target member pages must not use source layout.
    old,new=dirs('target-pages')
    for i in range(1000):
        source_offset(old,3+i,100+i,True)
        source_member(old,100+i,0xf0000000+i,5,True)
    assert run(old,new,True,3,1003,1100)==(1003,1001)
    for i in range(1000):
        assert target_offset(new,3+i)==i+1
        assert target_member(new,i+1)==(0xf0000000+i,5)
    for raw,source_base,expected in [(1,0xfffffffe,2**32),(1,2**32,2**32),
                                     (2,2**32+1,2**32+1),(0xffffffff,0xfffffffe,0xffffffff)]:
        result=subprocess.run([str(exe),'map',str(raw),str(source_base)],capture_output=True,text=True,check=True)
        assert int(result.stdout)==expected,result
        count+=1
    old,new=dirs('offset-wrap')
    source_offset(old,3,0xfffffffe,False)
    for off,xid,status in [(0xfffffffe,10,1),(0xffffffff,20,5),(0,0,0),(1,30,1)]:
        source_member(old,off,xid,status,False)
    assert run(old,new,False,3,4,2)==(4,2) and target_member(new,1)==(20,5)
    for label,start,endoff,members in [
        ('reverse',100,99,[]), ('oversize',100,100+2**31,[]),
        ('double-updater',100,102,[(100,1,4),(101,2,5)])]:
        old,new=dirs(label); source_offset(old,3,start,True)
        for off,xid,status in members: source_member(old,off,xid,status,True)
        run(old,new,True,3,4,endoff,ok=False)
    # CLOG full control XID includes epoch: addresses remain raw uint32.
    for label,oldest,nextxid,pages in [
        ('clog-epoch',32768,3*2**32+3*32768,[1,2]),
        ('clog-wrap',0xffff8000,5*2**32+32768,[131071,0]),
        ('clog-empty',100,2**32+100,[0])]:
        old,new=tmp/(label+'-old'),tmp/(label+'-new'); old.mkdir(); new.mkdir()
        for page in pages: put(old,page,0,bytes([page%251+1])*8192,False)
        result=subprocess.run([str(exe),'clog',str(old),str(new),str(oldest),str(nextxid)],capture_output=True,text=True)
        assert result.returncode==0,result
        for page in pages:
            with page_path(new,page,True).open('rb') as f:
                f.seek((page%32)*8192); assert f.read(8192)==bytes([page%251+1])*8192
        count+=1
    for major,cat,wide in [(180000,202506291,False),(190000,202607272,True),
                           (190000,202512090,False),(90200,201204301,False)]:
        old,new=dirs(f'dispatch-{major}-{cat}')
        clog=old/('pg_clog' if major <= 90600 else 'pg_xact'); clog.mkdir()
        (new/'pg_xact').mkdir()
        put(clog,0,0,bytes([0x55])*8192,False)
        off=2**32+10 if wide else 10
        if major != 90200:
            source_offset(old,3,off,wide); source_offset(old,4,off+1,wide)
            source_member(old,off,200,5,wide); source_member(old,off+1,201,1,wide)
        result=subprocess.run([str(sql_exe),'dispatch',str(old),str(new),str(major),'4',str(cat),
                               '3','5',str(off+2),'3',str(3*2**32+10)],capture_output=True,text=True)
        assert result.returncode==0,result
        assert 'runtime error' not in result.stderr,result.stderr
        expected=(2**32,5,5 if major == 90200 else 3,1 if major == 90200 else 3)
        assert f'RESULT|{"|".join(map(str,expected))}' in result.stdout,result.stdout
        assert ' -e ' not in result.stdout and 'COPY|' not in result.stdout,result.stdout
        assert f' -m 5,{expected[2]} ' in result.stdout,result.stdout
        count+=1
    # A checkpoint can hold the raw next-MXID zero immediately after wrap.
    for wide in [False,True]:
        old,new=dirs(f'dispatch-zero-next-{wide}')
        (old/'pg_xact').mkdir(); (new/'pg_xact').mkdir()
        put(old/'pg_xact',0,0,bytes([0x55])*8192,False)
        source_offset(old,0xffffffff,100,wide); source_member(old,100,200,5,wide)
        result=subprocess.run([str(sql_exe),'dispatch',str(old),str(new),
                               '190000' if wide else '180000','4',
                               '202607272' if wide else '202506291',
                               str(0xffffffff),'0','101','3',str(3*2**32+10)],capture_output=True,text=True)
        assert result.returncode==0,result
        assert f'RESULT|{2**32}|{2**32}|{2**32-1}|2' in result.stdout,result.stdout
        assert target_member(new,1)==(200,5)
        count+=1
    # Already-xid64 path must keep full counters and normalize old 12-digit names.
    old,new=dirs('dispatch-xid64-copy')
    (new/'pg_xact').mkdir()
    for folder in [new/'pg_xact',new/'pg_multixact/offsets',new/'pg_multixact/members']:
        (folder/'000000000ABC').write_bytes(b'unchanged')
    result=subprocess.run([str(sql_exe),'dispatch',str(old),str(new),'150000','8','202209061',
                           str(2**32+3),str(2**32+5),str(2**33),'3',str(2**34)],capture_output=True,text=True)
    assert result.returncode==0,result
    assert result.stdout.count('COPY|')==3 and 'REMOVE|' not in result.stdout,result.stdout
    assert f'RESULT|{2**34}|{2**32+5}|{2**32+3}|{2**33}' in result.stdout,result.stdout
    for folder in [new/'pg_xact',new/'pg_multixact/offsets',new/'pg_multixact/members']:
        assert (folder/'000000000000ABC').read_bytes()==b'unchanged'
        assert not (folder/'000000000ABC').exists()
    count+=1
    # Inspect actual emitted horizon SQL: XID-only reset must preserve MXID cutoffs.
    for preserve,minonly,wrapped in [(1,0,False),(1,0,True),(0,0,True),(0,1,False)]:
        nextmulti=2**32+2 if wrapped else 100
        result=subprocess.run([str(sql_exe),'horizons',str(0xfffffffe),str(nextmulti),
                               str(preserve),str(minonly)],capture_output=True,text=True,check=True)
        sql=result.stdout
        assert ('SET\tdatfrozenxid' in sql)==(not minonly),sql
        assert ('SET\trelfrozenxid' in sql)==(not minonly),sql
        assert ('SET\tdatminmxid' in sql)==(not preserve),sql
        assert ('SET\trelminmxid' in sql)==(not preserve),sql
        assert ('+ 4294967295' in sql)==wrapped,sql
        if not minonly: assert "datfrozenxid = '3'" in sql,sql
        if wrapped:
            assert sql.count('bigint < 4294967294')==3,sql
            assert sql.count('bigint > 0')==3,sql
        assert sql.count('ALLOW_CONNECTIONS = true')==sql.count('ALLOW_CONNECTIONS = false'),sql
        count+=1
    print(f'PASS: {count} actual-reader/rewriter/CLOG cases with real synthetic SLRU files, uint64 target XIDs and UBSan; source offset widths, high offsets, page boundaries, wraps, invalid entries and epoch stripping. Includes real dispatch and horizon functions with SQL/command fixtures; no live server upgrade tested.')
