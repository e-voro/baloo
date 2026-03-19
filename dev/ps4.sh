source ${DBG_BALOO_DIR}/dev/colours.sh

#export PS4="\[\e[1;33m\]+ \[\e[1;32m\]\$(date "+%Y%m%d:%H%M%S.%N") \[\e[1;34m\]\$(basename \${BASH_SOURCE})\[\e[1;35m\]:\[\e[1;31m\]\${LINENO}\[\e[0m\]: "
export PS4="$PURPLE\$(basename \${BASH_SOURCE})$PURPLE:$RED\${LINENO}: $NO_COLOR"
