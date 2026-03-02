#!/usr/bin/bash
# File:    dev/cfg.sh
# Created: 02.03.2026
# Author:  Evgeny Voropaev

# Staple debug build
CFLAGS="-O0 -g3 -pipe -Wno-missing-braces -fno-inline"
#CFLAGS="-O0 -g3 -pipe -Werror -Wno-missing-braces -fno-inline"

# Debug build with allocation sanity checking
#CFLAGS="-O0 -g3 -pipe -Wno-missing-braces -fsanitize=address -fno-omit-frame-pointer"
#LDFLAGS="-fsanitize=address"

echo "========================================================="
echo "BALOO: STARTED CONFIGURING =============================>"
echo "========================================================="
set -x
    ./configure --prefix="${DBG_INST_DIR}" \
        CFLAGS="$CFLAGS" \
        LDFLAGS="$LDFLAGS" \
        --with-icu \
        --enable-tap-tests \
        --enable-debug \
        --enable-cassert \
        --enable-depend \
        --enable-injection-points
set +x
echo "========================================================="
echo "BALOO: FINISHED CONFIGURING"
echo "========================================================="
