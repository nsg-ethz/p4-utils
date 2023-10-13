#!/bin/bash

# p4-utils branch 
P4_UTILS_BRANCH="master"

install_p4utils() {
    pip3 install -e "."
}

mx() {

    BINDIR=/usr/bin
    MANDIR=/usr/share/man/man1

    UTILSDIR=utils

    cd ${UTILSDIR}

    #compile mxexec
    cc -Wall -Wextra -DVERSION=\"1.4\" mxexec.c -o mxexec
    #create man page
    help2man -N -n "Mininet namespace execution utility" -h "-h" -v "-v" --no-discard-stderr ./mxexec -o mxexec.1

    #install
    install mxexec ${BINDIR}
    install mx ${BINDIR}
    install mxexec.1 ${MANDIR}

    cd ..
}

PY3LOCALPATH=`curl -sSL https://raw.githubusercontent.com/nsg-ethz/p4-utils/${P4_UTILS_BRANCH}/install-tools/scripts/py3localpath.py | python3`
function site_packages_fix {
    local SRC_DIR
    local DST_DIR

    SRC_DIR="${PY3LOCALPATH}/site-packages"
    DST_DIR="${PY3LOCALPATH}/dist-packages"

    # When I tested this script on Ubunt 16.04, there was no
    # site-packages directory.  Return without doing anything else if
    # this is the case.
    if [ ! -d ${SRC_DIR} ]; then
	    return 0
    fi

    echo "Adding ${SRC_DIR} to Python3 path..."
    sudo su -c "echo '${SRC_DIR}' > ${DST_DIR}/p4-tools.pth"
    echo "Done!"
}

install_p4utils
mx
site_packages_fix
