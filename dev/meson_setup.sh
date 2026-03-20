#!/usr/bin/bash
source ${DBG_BALOO_DIR}/dev/colours.sh

echo_green "========================================================="
echo_green "BALOO: STARTED MESON's SETUP =========>"
echo_green "========================================================="

source ${DBG_BALOO_DIR}/dev/ps4.sh

echo "Turning on 'set -x'"
[[ $- == *x* ]] && was_xtrace_on=true || was_xtrace_on=false
set -x

cd ${DBG_PROJ_DIR}

meson setup \
	--auto-features=disabled \
	--buildtype=debug \
	--prefix=${DBG_INST_DIR} \
	-Dcassert=true \
	-Ddefault_library=shared \
	-Dtap_tests=enabled \
	-DPG_TEST_EXTRA='wal_consistency_checking' \
	build

cd -

if [ "$was_xtrace_on" = false ]; then set +x; fi

echo_green "========================================================="
echo_green "BALOO: FINISHED MESON's SETUP"
echo_green "========================================================="

# ------------------------------------------------------------------------------
# Some examples and tips
# ------------------------------------------------------------------------------
#
# meson configure build \
#   --buildtype=debug \
#   -Dassert=true \
#   --auto-features=disabled \
#   -Ddefault_library=shared \
#   -Dtap_tests=enabled
#
# Use: meson configure build -Dassert=true → when toggling options
#
# Use: meson setup --reconfigure build → when meson.build or dependencies changed
#
# Use: meson configure build | grep buildtype for checking a setting and avoid
#   reconfiguring
#
# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------
#
# meson test -C build --list
# meson test -C build
#
# Run regress tests only:
#
# (all of them) meson test -C build --suite setup --suite regress
#
# verbose meson test -C build --suite setup --suite regress -v
#
# certain test or tests. It can result in fails. You might want use parallel schedule
#   TESTS="boolean select sqljson" meson test -C build --suite regress -v
#
#
# Run tests against a running instance:
#
#   meson test --setup running
#
# Use this if you already have a PostgreSQL server active and want to test against it.


# Set PG_TEXT_EXTRA through the meson configuration:
# 1. Update the configuration
#	meson configure build -DPG_TEST_EXTRA='ssl ldap wal_consistency_checking'
# 2. Run the test
#	meson test -v -C build "recovery/027_stream_regress"
#
# Set PG_TEXT_EXTRA through the environment variable:
# 	PG_TEST_EXTRA='ssl ldap wal_consistency_checking' meson test -v -C build "recovery/027_stream_regress"
