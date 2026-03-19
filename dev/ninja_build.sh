#!/usr/bin/bash
source ${DBG_BALOO_DIR}/dev/colours.sh

echo_green "========================================================="
echo_green "BALOO: STARTED BUILDING with NINJA =========>"
echo_green "========================================================="

source ${DBG_BALOO_DIR}/dev/ps4.sh

echo "Turning on 'set -x'"
[[ $- == *x* ]] && was_xtrace_on=true || was_xtrace_on=false
set -x

cd ${DBG_PROJ_DIR}

ninja -C build -v
# ninja -C build install
# ninja -C build tmp_check-install
# ninja -C build src/backend/utils/misc/install
# ninja -C build install-data
# ninja -C build tmp_install

cd -

if [ "$was_xtrace_on" = false ]; then set +x; fi

echo_green "========================================================="
echo_green "BALOO: FINISHED BUILDING with NINJA"
echo_green "========================================================="
