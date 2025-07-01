#!/usr/bin/bash
# File:    test.sh
# Created: 01.07.2025
# Author:  Evgeny Voropaev

# Calculate the project directory relative to the script location
DBG_PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"

make check
#make check-world
#make -C "$DBG_PROJ_DIR" check-world PG_TEST_EXTRA="wal_consistency_checking xid_wraparound "
#make -C "$DBG_PROJ_DIR" check-world \
#          PG_TEST_EXTRA=" ssl \
#                          ldap \
#                          kerberos \
#                          load_balance \
#                          xid_wraparound \ 
#                          libpq_encryption \
#                          wal_consistency_checking" \
#          PG_REGRESS_DIFF_OPTS=-ud \
#          PGOPTIONS="-c log_error_verbosity=verbose -c log_min_messages=debug2"
#
#make -C "$DBG_PROJ_DIR" check
#make -C "$DBG_PROJ_DIR/src/bin/pg_amcheck" check
#make -C "$DBG_PROJ_DIR/src/bin/pg_amcheck" check PROVE_TESTS="t/004_verify_heapam.pl"
#make -C "$DBG_PROJ_DIR/src/bin/pg_amcheck" check PROVE_TESTS="t/004_verify_heapam.pl" PROVE_FLAGS=" --verbose --exec 'perl -d -I ${DBG_PROJ_DIR}/src/test/perl/ -I . -Ilib -Ilocal/lib/perl5'"
#make -C "$DBG_PROJ_DIR/src/test/recovery/" check PROVE_TESTS="t/027_stream_regress.pl" PG_TEST_EXTRA="wal_consistency_checking"
#make -C "$DBG_PROJ_DIR/src/test/recovery/" check PROVE_TESTS="t/043_single_tuple_page_logical_backup.pl" PROVE_FLAGS=" --verbose --exec 'perl -d -I ${DBG_PROJ_DIR}/src/test/perl/ -I . -Ilib -Ilocal/lib/perl5'"
