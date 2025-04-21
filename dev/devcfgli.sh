#!/usr/bin/bash
# File:    devcfgcli.sh
# Created: 06.09.2024
# Author:  Evgeny Voropaev

# ==============================================================================
# Examples of usage:
#
# # Being in the top directory of the project, include helpers into your current terminal session:
#   source baloo/dev/devcfgcli.sh
#
# # Generate a script that comprises a sequence of applying patches:
#   bl_create_patching_file <edition_name>
#   # Example: create_patching_file se
#
# # If a patch from the sequence has been successfully applied, you will see commits added
# # to the current branch, and the local git state will be clean (except for files in the baloo directory).
#
# # You can also clear local changes by using the function:
#   bl_clear_project_dir
#
# # Split a patch into mini-patches, each for a single file, and create a script to apply them:
#   bl_split_patch <patch_file>
#   # Example: bl_split_patch baloo/patches/fix/common/my_patch.patch
#
# # Clean up all mini-patches and related scripts:
#   bl_clean_patch_cache
# ==============================================================================

# Calculate the project directory relative to the script location
DBG_PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.."; pwd)"
DBG_BALOO_DIR="${DBG_PROJ_DIR}/baloo"
DBG_PATCH_DIR="${DBG_BALOO_DIR}/patches"
DBG_PATCH_CACHE_DIR=${DBG_BALOO_DIR}/dev/cache/patches
DBG_INST_DIR=${DBG_PROJ_DIR}/baloo/dev/inst
DBG_INST_PORT=5888
DBG_COPT="-Werror"
DBG_HOST="localhost"
DBG_DEVCFGCLI_SCRIPT="$(cd $(dirname ${BASH_SOURCE}); pwd)/$(basename ${BASH_SOURCE})"

# Function to apply patches, stage changes, and commit
dbg_apply_patch() {
    local patch="$1"

    # Extract relative path for commit message
    local relative_patch_path="${patch#${DBG_PROJ_DIR}/}"

    set +x
    echo "========================================================="
    echo "STARTED APPLYING THE ${patch}"
    echo "========================================================="
    set -x

    git apply -v "${patch}"

    set +x
    echo "-------------------------------------------------------------"
    echo "The patch ${patch} has been SUCCESSFULLY APPLIED."
    echo "-------------------------------------------------------------"
    set -x

    git add . ':!baloo'
    git commit -m "Applied the ${relative_patch_path}."

    set +x
    echo "-------------------------------------------------------------"
    echo "CREATED THE COMMIT COMPRISING FILES MODIFIED BY THE ${relative_patch_path} PATCH."
    echo "-------------------------------------------------------------"
    set -x
}

dbg_am_patch() {
    local patch="$1"

    # Extract relative path for commit message
    local relative_patch_path="${patch#${DBG_PROJ_DIR}/}"

    set +x
    echo "========================================================="
    echo "STARTED APPLYING THE ${patch}"
    echo "========================================================="
    set -x

    git am "${patch}"

    set +x
    echo "-------------------------------------------------------------"
    echo "The patch ${patch} has been SUCCESSFULLY APPLIED and COMMITED."
    echo "-------------------------------------------------------------"
    set -x
}

# Function to clear the project directory, restoring to the last commit and removing untracked files, excluding the 'baloo' directory
dbg_clean_project_dir() {
    git restore --source=HEAD --worktree -- ":(exclude)${DBG_BALOO_DIR}/*" ':(exclude).gitlab-ci.yml'
    git clean -fdx -- ":(exclude)${DBG_BALOO_DIR}/*"
}

# Function to clean up all mini-patches and related scripts
dbg_clean_patch_cache() {
    echo "Cleaning up patch cache..."
    rm -rf "${DBG_PATCH_CACHE_DIR}"
    echo "Cleanup complete."
}

# Function to create a patch from local changes
dbg_retrieve_diff_from_local_changes() {
    local base_commit="$1"

    git add . ':!.gitlab-ci.yml' ':!baloo'
    mkdir -p  ${DBG_BALOO_DIR}/dev/cache/patches

    if [ -z "$base_commit" ]; then
        base_commit="HEAD"
    fi

    git diff --staged --patch --stat $base_commit -- ':!.gitlab-ci.yml' ':!baloo' > ${DBG_PATCH_CACHE_DIR}/diff_from_local_changes.patch

    git restore --staged -- '*'
}

# Function to split a patch into mini-patches, each containing changes for a single file
dbg_split_patch() {
    local patch_file="$1"
    local patch_name=$(basename "$patch_file" .patch)
    local output_dir="${DBG_PATCH_CACHE_DIR}/mini/${patch_name}"
    local apply_script="${DBG_PATCH_CACHE_DIR}/mini/apply_${patch_name}_minis.sh"

    # Check if the patch file exists, and if not, try to locate it in DBG_PATCH_DIR
    if [[ ! -f "$patch_file" ]]; then
        patch_file="${DBG_PATCH_DIR}/${patch_file}"
        if [[ ! -f "$patch_file" ]]; then
            echo "Error: Patch file ${patch_file} not found."
            return 1
        fi
    fi

    mkdir -p "$output_dir"

    # Get the absolute path of the output directory
    local abs_output_dir=$(cd "$output_dir"; pwd)

    # Split the patch file into mini-patches, one per file with 4-digit numbering
    local mini_patch_num=1
    awk '
    /^diff --git/ {
        if (f) close(f)
        f=sprintf("'"$abs_output_dir"'/mini%04d-%s.patch", mini_patch_num++, "'"$patch_name"'")
    }
    { if (f) print > f }
    END { if (mini_patch_num == 1) exit 1 }
    ' "$patch_file"

    if [[ $? -ne 0 ]]; then
        echo "Error: No valid diffs found in the patch file."
        return 1
    fi

    echo "Split patch created in ${abs_output_dir}"


    # Generate the script to apply the mini-patches

    cat > "$apply_script" << EOL
#!/usr/bin/bash
# Automatically generated script for applying mini-patches for ${patch_name}

MINI_PATCH_DIR="${abs_output_dir}"
PATCH_NAME="${patch_name}"
DEVCFGCLI_SCRIPT="${DBG_DEVCFGCLI_SCRIPT}"

# Enhanced PS4 with timestamp and source info for debugging
PS4='\[\e[1;33m\]+ \[\e[1;32m\]\$(date "+%Y%m%d:%H%M%S.%N") \[\e[1;34m\]\$(basename \${BASH_SOURCE})\[\e[1;35m\]:\[\e[1;31m\]\${LINENO}\[\e[0m\]: '

# Set shell options: -e (exit on error), -x (trace commands), -u (unset variables as an error), -o pipefail (pipe status)
set -exu -o pipefail

# Logfile setup
LOGFILE="\${MINI_PATCH_DIR}/apply_\${PATCH_NAME}_minis.log"
exec &> >(tee -a "\${LOGFILE}")

source "\${DEVCFGCLI_SCRIPT}"

EOL

    for mini_patch in "$abs_output_dir"/*.patch; do
        local mini_patch_name=$(basename "$mini_patch")
        echo "dbg_apply_patch \"\${MINI_PATCH_DIR}/${mini_patch_name}\" " >> "$apply_script"
    done

    chmod +x "$apply_script"
    echo "Script $apply_script has been created."
}

# Function to validate the edition name and create a corresponding apply patch file
dbg_create_patching_script_for_edition() {
    local edition_name="$1"

    local config_file="${DBG_BALOO_DIR}/conf.json"
    local patches_dir="${DBG_BALOO_DIR}/patches"
    local output_script_dir="${DBG_PATCH_CACHE_DIR}"
    local edition_cfg=$(jq -r ".editions.${edition_name}" "$config_file")

    if [[ ! $edition_cfg || "null" == "$edition_cfg" ]]; then
        echo "Error: Invalid edition name '${edition_name}'. There is no this edition in the configuration (conf.json)."
        return 1
    fi

    local edition_full_name=$(jq -r ".editions.${edition_name}.name" "$config_file")


    mkdir -p "$output_script_dir"

    local patch_group=$(jq -r ".editions.${edition_name}.patches[]" "$config_file")

    local output_script="${output_script_dir}/apply_${edition_name}.sh"

    if [ -f "$output_script" ]; then
        local backup_num=1
        local backup_file="${output_script}.${backup_num}"
        while [ -f "$backup_file" ]; do
            backup_num=$((backup_num + 1))
            backup_file="${output_script}.${backup_num}"
        done
        mv "$output_script" "$backup_file"
        echo "Existing script backed up as $backup_file"
    fi

    cat > ${output_script} << EOL
#!/usr/bin/bash
# Automatically generated script for applying patches groups for the ${edition_name} edition of the customized PostgreSQL project (Baloo)
# Created by the function 'dbg_create_patching_file' from the script ${DBG_DEVCFGCLI_SCRIPT}

# Set shell options: -e (exit on error), -x (trace commands), -u (unset variables as an error), -o pipefail (pipe status)
set -exu -o pipefail

# Determine the directory where the script is located
SCRIPT_DIR=\$(cd "\$(dirname "\${BASH_SOURCE}")"; pwd)

DEVCFGCLI_SCRIPT="${DBG_DEVCFGCLI_SCRIPT}"

source "\${DEVCFGCLI_SCRIPT}"

# Enhanced PS4 with timestamp and source info for debugging
PS4='\[\e[1;33m\]+ \[\e[1;32m\]\$(date "+%Y%m%d:%H%M%S.%N") \[\e[1;34m\]\$(basename \${BASH_SOURCE})\[\e[1;35m\]:\[\e[1;31m\]\${LINENO}\[\e[0m\]: '

# Logfile setup
LOGFILE="\${SCRIPT_DIR}/applying_patches_${edition_name}.log"
exec &> >(tee -a "\${LOGFILE}")

EOL

    cat >> ${output_script} << EOL
    # Alternative approach for applying patches.
EOL

    for patch in $patch_group; do
        local patch_files=$(find "${DBG_PATCH_DIR}/${patch}" -type f -name "*.patch" | sort)
        for file in $patch_files; do
            local relative_path="${file#${DBG_PATCH_DIR}/}"
            echo "dbg_apply_patch \"\${DBG_PATCH_DIR}/${relative_path}\"" >> "$output_script"
        done
    done

    cat >> ${output_script} << EOL
    # Alternative approach for applying patches.
EOL

    for patch in $patch_group; do
        local patch_files=$(find "${DBG_PATCH_DIR}/${patch}" -type f -name "*.patch" | sort)
        for file in $patch_files; do
            local relative_path="${file#${DBG_PATCH_DIR}/}"
            echo "# dbg_am_patch \"\${DBG_PATCH_DIR}/${relative_path}\"" >> "$output_script"
        done
    done

    chmod +x "$output_script"
    echo "Script $output_script has been created."
}

dbg_configure() {
    local CFLAGS="-O0 -g3 -pipe -Wno-missing-braces"
    # local CFLAGS="-O0 -g3 -pipe -Werror -Wno-missing-braces"
    echo "========================================================="
    echo "BALOO: STARTED CONFIGURING =============================>"
    echo "========================================================="
    set -x
        ./configure --prefix="${DBG_INST_DIR}" \
            CFLAGS="$CFLAGS" \
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
}

dbg_build_core() {
    echo "========================================================="
    echo "BALOO: STARTED BUILDING CORE =========>"
    echo "========================================================="

    cd "${DBG_PROJ_DIR}"
    make COPT='${DBG_COPT}' -j5
    cd -

    echo "========================================================="
    echo "BALOO: FINISHED BUILDING CORE "
    echo "========================================================="
}

dbg_build_contribs() {
    echo "========================================================="
    echo "BALOO: STARTED BUILDING CONTRIBS =========>"
    echo "========================================================="

    cd "${DBG_PROJ_DIR}/contrib"
    make COPT='${DBG_COPT}' -j5
    cd -

    echo "========================================================="
    echo "BALOO: FINISHED BUILDING CONTRIBS "
    echo "========================================================="
}

dbg_install() {
    echo "========================================================="
    echo "BALOO: STARTED INSTALLING =============================>"
    echo "========================================================="
    set -x
    cd "${DBG_PROJ_DIR}"
    make install
    cd -
    set +x

    echo "---------------------------------------------------------"
    echo "CREATING INSTALLATION HELPERS in ${DBG_INST_DIR}/instcfgcli.sh"
    echo "---------------------------------------------------------"

    local installation_cli_configurator="${DBG_INST_DIR}/instcfgcli.sh"
            cat >"${installation_cli_configurator}" << EOF
#!/usr/bin/bash
export PGINSTDIR="${DBG_INST_DIR}"
export PGDATA="${DBG_INST_DIR}/data"
export PGPORT="${DBG_INST_PORT}"
export PGUSER="$(whoami)"
export PGDATABASE="postgres"
export PGHOST="${DBG_HOST}"
export PATH="${DBG_INST_DIR}/bin:\$PATH"
LD_LIBRARY_PATH=\${LD_LIBRARY_PATH:-''}
export LD_LIBRARY_PATH="\${PGINSTDIR}/lib:\${LD_LIBRARY_PATH}"
export PSQLRC="${DBG_INST_DIR}/.psqlrc"

inst_init() {
    echo "========================================================="
    echo "BALOO: CLUSTER INITIALISATION"
    echo "========================================================="

    initdb -D \$PGDATA
    # initdb -D $PGDATA -A trust -N -x 1249835483136 -m 2422361554944 -o 3594887626752

    echo "---------------------------------------------------------"
    echo "Configuring PORT and SOCKET"
    echo "---------------------------------------------------------"
    echo "port=\$PGPORT"                    >> \$PGDATA/postgresql.conf #Change it to substitution with SED
    echo "unix_socket_directories='/tmp'"   >> \$PGDATA/postgresql.conf

    #echo "---------------------------------------------------------"
    #echo "Configuring SHARED PRELOAD LIBRARIES"
    #echo "---------------------------------------------------------"
    #echo "shared_preload_libraries='online_analyze,plantuner,dbcopies_decoding'" >> \$PGDATA/postgresql.conf

    echo "---------------------------------------------------------"
    echo "Configuring logical replication"
    echo "---------------------------------------------------------"

    echo "wal_level = 'logical'"            >> \$PGDATA/postgresql.conf
    echo "max_replication_slots = 1"        >> \$PGDATA/postgresql.conf
    echo "max_wal_senders = 4"              >> \$PGDATA/postgresql.conf
    echo "shared_preload_libraries='test_decoding'" >> \$PGDATA/postgresql.conf

    echo "========================================================="
    echo "BALOO: CLUSTER INITIALISATION FINISHED"
    echo "========================================================="
}

inst_start() {
    echo "========================================================="
    echo "BALOO: CLUSTER START"
    echo "========================================================="

    pg_ctl -D \$PGDATA -l \$PGDATA/logfile start

    echo "========================================================="
    echo "BALOO: CLUSTER START FINISHED"
    echo "========================================================="
}

inst_stop() {
    echo "========================================================="
    echo "BALOO: CLUSTER STOP"
    echo "========================================================="

    pg_ctl -D \$PGDATA stop

    echo "========================================================="
    echo "BALOO: CLUSTER STOP FINISHED"
    echo "========================================================="
}
EOF
    echo "========================================================="
    echo "FINISHED INSTALLING"
    echo "========================================================="
}

dbg_install_contribs() {
    echo "========================================================="
    echo "BALOO: STARTED INSTALLING CONTRIBS =========>"
    echo "========================================================="

    cd "${DBG_PROJ_DIR}/contrib"
    make install
    cd -

    echo "========================================================="
    echo "BALOO: FINISHED INSTALLING CONTRIBS "
    echo "========================================================="
}


dbg_generate_support_of_tantor_installation(){
    local TT_VER="16"
    local TT_ED="se-1c"
    cat > ttinstcfgcli.sh << EOF
#!/usr/bin/bash
export PGINSTDIR="/opt/tantor/db/${TT_VER}"
export PATH="\${PGINSTDIR}/bin:\$PATH"
export PGDATA="/var/lib/postgresql/tantor-${TT_ED}-${TT_VER}/data"
EOF
}

dbg_test() {
    make -C "$DBG_PROJ_DIR" check-world PG_TEST_EXTRA="wal_consistency_checking xid_wraparound "
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
}

dbg_generate_debug_config_for_vscode(){
    mkdir -p "$DBG_PROJ_DIR/.vscode"
    cat > "$DBG_PROJ_DIR/.vscode/tasks.json" << EOF
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Del data-dir",
      "type": "shell",
      "command": "rm -rf ${DBG_INST_DIR}/data",
      "options": { "cwd": "${DBG_PROJ_DIR}" }
    },
  ]
}
EOF

    cat > "$DBG_PROJ_DIR/.vscode/inst.env" << EOF
PGDATA="${DBG_INST_DIR}/data"
PGPORT="${DBG_INST_PORT}"
PGUSER="$(whoami)"
PGDATABASE="postgres"
PGHOST="localhost"
PATH="${DBG_INST_DIR}/bin:${PATH}"
LD_LIBRARY_PATH="${PGINSTDIR}/lib:${LD_LIBRARY_PATH}"
PSQLRC="${DBG_INST_DIR}/.psqlrc"
EOF


    cat > "$DBG_PROJ_DIR/.vscode/launch.json" << EOF
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Debug postgres",
            "type": "cppdbg",
            "request": "attach",
            "program": "${DBG_INST_DIR}/bin/postgres",
            "MIMode": "gdb",
            "setupCommands": [
                {
                    "description": "Enable pretty-printing for gdb",
                    "text": "-enable-pretty-printing",
                    "ignoreFailures": true
                },
                {
                    "description": "Set Disassembly Flavor to Intel",
                    "text": "-gdb-set disassembly-flavor intel",
                    "ignoreFailures": true
                }
            ]
        },
        {
            "name": "Debug postgres --boot",
            "type": "cppdbg",
            "request": "launch",
            "program": "${DBG_INST_DIR}/bin/postgres",
            "args": [
                "--boot", "-F", "-c",
                "log_checkpoints=false",
                "-X", "16777216",
                "-m", "2422361554944",
                "-o", "3594887626752",
                "-x", "1249835483136",
                "-k"
            ],
            "MIMode": "gdb",
            "setupCommands": [
                {
                    "description": "Enable pretty-printing for gdb",
                    "text": "-enable-pretty-printing",
                    "ignoreFailures": true
                },
                {
                    "description": "Set Disassembly Flavor to Intel",
                    "text": "-gdb-set disassembly-flavor intel",
                    "ignoreFailures": true
                }
            ],
            "externalConsole": false,
            "miDebuggerPath": "/usr/bin/gdb",
            "stopAtEntry": false,
            "cwd": "${DBG_PROJ_DIR}",
            "envFile": "$DBG_PROJ_DIR/.vscode/inst.env",
            "comment" : "We are going to see something similar to bin/postgres --boot -F -c log_checkpoints=false  -X 16777216 -m 2422361554944 -o 3594887626752 -x 1249835483136 -k"
        },
        {
            "name": "Debug initdb",
            "type": "cppdbg",
            "request": "launch",
            "preLaunchTask": "Del data-dir",
            "program": "${DBG_INST_DIR}/bin/initdb",
            "dummy_args": [],
            "args": [
                "--no-clean",
                "--no-sync",
                "-x", "1249835483136",
                "-m", "2422361554944",
                "-o", "3594887626752",
                "--no-locale"
            ],
            "stopAtEntry": false,
            "cwd": "${DBG_PROJ_DIR}",
            "envFile": "$DBG_PROJ_DIR/.vscode/inst.env",
            "externalConsole": false,
            "MIMode": "gdb",
            "setupCommands": [
              {
                "description": "Enable pretty-printing for gdb",
                "text": "-enable-pretty-printing",
                "ignoreFailures": true
              }
            ],
            "miDebuggerPath": "/usr/bin/gdb"
        },
        {
            "name": "Debug pg_recvlogical",
            "type": "cppdbg",
            "request": "launch",
            "program": "${DBG_INST_DIR}/bin/pg_recvlogical",
            "args": [
                "-d", "postgres",
                "-p", "${DBG_INST_PORT}",
                "-h", "localhost",
                "-S", "my_slot",
                "--start",
                "-f", "${DBG_INST_DIR}/data/pg_recvlogical.log"
            ],
            "stopAtEntry": false,
            "cwd": "${DBG_PROJ_DIR}",
            "envFile": "$DBG_PROJ_DIR/.vscode/inst.env",
            "externalConsole": false,
            "MIMode": "gdb",
            "setupCommands": [
              {
                "description": "Enable pretty-printing for gdb",
                "text": "-enable-pretty-printing",
                "ignoreFailures": true
              }
            ],
            "miDebuggerPath": "/usr/bin/gdb"
        },
        {
            "name": "Debug pg_ctl",
            "type": "cppdbg",
            "request": "launch",
            "program": "${DBG_INST_DIR}/bin/pg_ctl/pg_ctl",
            "args": ["-D", "${DBG_INST_DIR}/data", "start"],
            "stopAtEntry": false,
            "cwd": "${DBG_PROJ_DIR}",
            "externalConsole": false,
            "MIMode": "gdb",
            "setupCommands": [
              {
                "description": "Enable pretty-printing for gdb",
                "text": "-enable-pretty-printing",
                "ignoreFailures": true
              }
            ],
            "environment": [
              {
                "name" : "VAR1",
                "value": "It is the example of use of the environment field"
              },
              {
                "name" : "ANOTHER_ENV_VAR",
                "value": "VAL2"
              }
            ],
            "preLaunchTask": "",
            "miDebuggerPath": "/usr/bin/gdb"
        },
        {
          // debugging remotely
          "name": "Remote Debug",
          "type": "cppdbg",
          "request": "attach",
          "MIMode": "gdb",
          "miDebuggerServerAddress": "REMOTE_IP:PORT",
          "miDebuggerPath": "/usr/bin/gdb",
          "program": "/path/to/local/postgres/executable",
          "setupCommands": [
            {
              "description": "Enable pretty-printing for gdb",
              "text": "-enable-pretty-printing",
              "ignoreFailures": true
            }
          ]
        }
    ]
}

EOF
}
