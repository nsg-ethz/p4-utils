#!/usr/bin/env python3
import argparse
import sys
import socket
import random
import struct
from threading import *

from scapy.all import *

sw = ''
rtr = sys.argv[1]

# Check if switch or router
if not rtr.startswith('r'):
    sw = rtr

def get_pkt():
    load_contrib('ospf')
    if len(sw) != 0:
        if len(sys.argv) == 2:
            print("please enter interface for switch as a second argument")
            exit(1)
        intf = str(sw) + "-" +str(sys.argv[2])
    else:
        intf = str(rtr) + "-eth0"

    sniff(iface=str(intf), prn = lambda x : x.show())

def main():

    if len(sys.argv)<1:
        print('pass 1 argument: router name')
        exit(1)

    get_pkt()

if __name__ == '__main__':
    main()
