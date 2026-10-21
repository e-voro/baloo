#!/usr/bin/env python3
"""Actual native swap/transfer functions and PostgreSQL checksums on synthetic files.

Tests filesystem operations, not running PostgreSQL servers. Clone/copy_file_range
and pre-9.6 VM payload conversion are outside this fixture.
"""
from pathlib import Path
import os
import re
import shlex
import struct
import subprocess
import sys
import tempfile
root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
here=Path(__file__).resolve().parent
upgrade=root/'src/bin/pg_upgrade'
rel=(upgrade/'relfilenumber.c').read_text()
file=(upgrade/'file.c').read_text()
header=(root/'src/include/storage/bufpage.h').read_text()
version=(upgrade/'version.c').read_text()
def function(source,signature):
    start=source.index(signature); opening=source.index('{',start); end,depth=opening+1,1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}'); end+=1
    return source[start:end]+'\n'
page_functions=''.join(function(header,sig) for sig in [
    'static inline bool\nPageIsNew(', 'static inline Size\nPageGetPageSize(',
    'static inline void\nPageSetPageSizeAndVersion('])
checksum=(root/'src/include/storage/checksum_impl.h').read_text()
checksum=checksum.replace('#include "storage/bufpage.h"','')
checksum=checksum.replace('#include "storage/checksum_block_internal.h"',
                          (root/'src/include/storage/checksum_block_internal.h').read_text())
functions=''.join(function(version,sig) for sig in ['bool\ncluster_is_xid64(', 'bool\ncluster_is_xid32('])
functions+=function(file,'void\nupdateSegmentPagesVersion(')
functions+=rel[rel.index('#define SYNC_QUEUE_MAX_LEN'):rel.index('/*\n * transfer_all_new_tablespaces()')]
for sig in ['static int\nFileNameMapCmp(', 'static RelFileNumber\nparse_relfilenumber(',
            'static bool\nprepare_for_swap(', 'static void\nrewrite_swap_fork(',
            'static void\nrewrite_swap_auxiliary_files(', 'static void\nswap_catalog_files(',
            'static void\ndo_swap(', 'static void\ntransfer_relfile(',
            'static void\ntransfer_single_new_db(']:
    functions+=function(rel,sig)
fixture=(here/'fixture.c').read_text().replace('/* PAGE FUNCTIONS */',page_functions)
fixture=fixture.replace('/* CHECKSUM */',checksum).replace('/* FUNCTIONS */',functions)
layout=int(re.search(r'#define PG_PAGE_LAYOUT_VERSION\s+(\d+)',header)[1])
fixture=fixture.replace('PAGE_VERSION',str(layout))
with tempfile.TemporaryDirectory(prefix='xid64-swap-aux-') as tmp:
    tmp=Path(tmp); code=tmp/'fixture.c'; code.write_text(fixture); exe=tmp/'fixture'
    subprocess.run(shlex.split(os.environ.get('CC','cc')) + [
        '-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=undefined',
        '-fno-sanitize-recover=all',str(code),'-o',str(exe)],check=True)
    def invoke(args,ok=True):
        result=subprocess.run([str(exe),*map(str,args)],capture_output=True,text=True)
        assert result.returncode==(0 if ok else 1),(args,result)
        assert 'runtime error' not in result.stderr,result.stderr
        return result.stdout.splitlines()
    def page(version,byte):
        data=bytearray([byte]*8192)
        data[:24]=struct.pack('=QHHHHHHI',17,77,0,24,8192,8192,8192|version,0)
        return bytes(data)
    def transformed(data):
        result=bytearray(data)
        for off in range(0,len(data),8192):
            if struct.unpack_from('=H',data,off+14)[0]:
                struct.pack_into('=H',result,off+18,8192|layout)
        return bytes(result)
    def prepare(label,width,checksums):
        path=tmp/label; sources=[]; main=[]; catalogs=[]
        for oldbase,newbase,rfn in [('old/base','new/base',50000),('oldts/PG_OLD','newts/PG_NEW',60000)]:
            old=path/oldbase/'16384'; new=path/newbase/'16384'
            old.mkdir(parents=True); new.mkdir(parents=True)
            (old/str(rfn)).write_bytes(b'original heap file')
            main.append((old/str(rfn),new/str(rfn),(old/str(rfn)).stat().st_ino))
            (new/str(rfn)).write_bytes(b'empty restored heap')
            for fork in ['_fsm','_vm']:
                for seg in [0,1]:
                    name=f'{rfn}{fork}'+('' if seg==0 else '.1')
                    pages=([page(4 if width==4 else layout,13),bytes(8192),
                            page(4 if width==4 else layout,37)]+([bytes(8192)]*5 if seg==0 else []))
                    target=old/name; target.write_bytes(b''.join(pages))
                    if checksums: invoke(['seal',target,seg*8])
                    sources.append((target,new/name,seg*8,target.read_bytes(),target.stat().st_ino))
            # Empty forks and absent forks are legal; preserve empty extents.
            (old/f'{rfn}_vm.2').touch()
            sources.append((old/f'{rfn}_vm.2',new/f'{rfn}_vm.2',16,b'',(old/f'{rfn}_vm.2').stat().st_ino))
            (old/'1259').write_bytes(b'old system catalog')
            (new/'1259').write_bytes(b'new restored catalog')
            (old/'1259_vm').write_bytes(page(4,5))
            newcat=new/'1259_vm'; newcat.write_bytes(page(layout,7))
            if checksums: invoke(['seal',newcat,0])
            catalogs.append((newcat,newcat.read_bytes()))
        return path,sources,main,catalogs
    count=0
    for mode in ['swap','partitioned','copy','link']:
        for width in [4,8]:
            for checksums in [0,1]:
                for sync in ([0,1] if mode in ['swap','partitioned'] else [1]):
                    path,sources,mains,catalogs=prepare(f'{mode}-{width}-{checksums}-{sync}',width,checksums)
                    log=invoke([mode,path,width,checksums,sync,0])
                    swapped=mode in ['swap','partitioned']
                    for old,new,first,original,inode in sources:
                        # The ordinary native transfer skips zero-length fork extents.
                        if not original and not swapped:
                            assert not new.exists(); continue
                        expected=transformed(original) if width==4 else original
                        exp=tmp/'expected'; exp.write_bytes(expected)
                        if checksums and expected: invoke(['seal',exp,first])
                        assert new.read_bytes()==exp.read_bytes(),(new,first)
                        if checksums and expected: invoke(['verify',new,first])
                        if not swapped: assert old.read_bytes()==original
                        if swapped and width==8: assert new.stat().st_ino==inode
                        if swapped and width==4 and expected:
                            temporary=str(new)+'.pg_upgrade'
                            rename=f'RENAME|{temporary}|{new}'
                            assert rename in log,log
                            directory=f'SYNCDIR|{new.parent}'
                            assert log.index(rename)<log.index(directory),log
                            fsync=f'SYNCFILE|{temporary}'
                            assert (fsync in log)==bool(sync),log
                            if sync: assert log.index(fsync)<log.index(rename),log
                    for old,new,inode in mains:
                        assert new.read_bytes()==b'original heap file'
                        if swapped or mode=='link': assert new.stat().st_ino==inode
                    for name,data in catalogs: assert name.read_bytes()==data
                    if swapped:
                        assert not (path/'old/base/16384').exists()
                        assert not (path/'oldts/PG_OLD/16384').exists()
                        for oldbase in ['old/base','oldts/PG_OLD']:
                            moved=path/oldbase/'moved_for_upgrade/16384_old_catalogs/1259'
                            assert moved.read_bytes()==b'old system catalog'
                        if not sync: assert not any(x.startswith('SYNCFILE|') for x in log),log
                        if width==8: assert not any('.pg_upgrade' in x for x in log),log
                    assert not list(path.rglob('*.pg_upgrade'))
                    count+=1
    for failure in ['corrupt','truncated','sync','existing-temp']:
        path,sources,_,_=prepare('failure-'+failure,4,1)
        old,new,_,_,_=sources[0]
        if failure=='corrupt':
            data=bytearray(old.read_bytes()); struct.pack_into('=H',data,12,25); old.write_bytes(data)
        if failure=='truncated': old.write_bytes(old.read_bytes()[:-1])
        if failure=='existing-temp': old.with_name(old.name+'.pg_upgrade').write_bytes(b'existing output')
        original=old.read_bytes()
        log=invoke(['swap',path,4,1,1,int(failure=='sync')],ok=False)
        assert new.read_bytes()==original,(failure,new)
        assert f'RENAME|{new}.pg_upgrade|{new}' not in log,log
        if failure=='existing-temp': assert Path(str(new)+'.pg_upgrade').read_bytes()==b'existing output'
        count+=1
    print(f'PASS: {count} swap/partitioned/copy/link filesystem scenarios; actual native rename/catalog/sync paths and PostgreSQL checksums, real synthetic FSM/VM segments, zero pages, xid64 no-op, tablespaces, fsync ordering and failure-before-replacement; UBSan. No server upgrade tested.')
