#!/bin/bash

install_p4utils() {
    pip install -e "."
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

install_p4utils
mx