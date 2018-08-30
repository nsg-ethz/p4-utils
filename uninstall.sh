#!/usr/bin/env bash

uninstall_p4utils() {
    pip uninstall p4utils
}

remove_mx() {

    BINDIR=/usr/bin
    MANDIR=/usr/share/man/man1

    rm -f ${BINDIR}/"mxexec"
    rm -f ${BINDIR}/"mx"
    rm -rf ${MANDIR}/"mxexec.1"

}

uninstall_p4utils
remove_mx