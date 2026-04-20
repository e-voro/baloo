#!/usr/bin/bash
# File:    dev/deb_asan.sh
# Created: 09.04.2026
# Author:  Evgeny Voropaev

# The same as in Dockerfile.pg-trixie-asan and in .cirrus.tasks.yml
CIRRUS_WORKING_DIR="/home/postgres/postgres"

echo "========================================================="
echo "BALOO: STARTED DEBIAN-ASAN JOB ====================>"
echo "========================================================="
set -x

#	docker build -f ${DBG_BALOO_DIR}/dev/docker/Dockerfile.pg-trixie-asan \
#			-t pg-trixie-asan:1.0 \
#			${DBG_BALOO_DIR}/dev/docker

	docker run	-it --privileged \
				-v ${DBG_PROJ_DIR}:${CIRRUS_WORKING_DIR} \
				--name pg-trixie-asan \
				pg-trixie-asan:1.0 \
				/bin/bash

#	Inside the having started docker container do:
#	./configure --enable-cassert \
#		--enable-injection-points \
#		--enable-debug \
#		--enable-tap-tests \
#		--with-segsize-blocks=6 \
#		${LINUX_CONFIGURE_FEATURES} \
#		CLANG="ccache clang"
#		#--enable-nls \
#		#--with-libnuma \
#		#--with-liburing \
set +x
echo "========================================================="
echo "BALOO: DEBIAN-ASAN JOB"
echo "========================================================="
