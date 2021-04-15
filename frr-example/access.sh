#!/bin/bash

if [ -z $1 ] ; then
    echo "Usage access <router_name>"
    exit 0
fi

sudo vtysh --vty_socket /var/run/$1