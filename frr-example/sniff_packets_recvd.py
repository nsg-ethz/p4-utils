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

if rtr.endswith('2'):
    list_of_ips = ["10.0.1.2", "10.2.0.2"]
elif rtr.endswith('1'):
    list_of_ips = ["10.0.1.1", "10.1.0.2"]

def get_pkt():
    load_contrib('ospf')
    if len(sw) != 0:
        if len(sys.argv) == 2:
            print("please enter interface for switch as a second argument")
            exit(1)
        intf = str(sw) + "-" +str(sys.argv[2])
    else:
        intf = str(rtr) + "-eth0"

    # Sniff packets on the CP routers incoming interface and filter messages which are sent by the router itself
    if rtr.startswith('r'):
        sniff(filter = "ip src {} or ip src {}".format(list_of_ips[0],list_of_ips[1]), iface=str(intf), prn = lambda x : x.show())
    
    else:
        sniff(iface=str(intf), prn = lambda x : x.show())

def main():

    if len(sys.argv)<1:
        print('pass 1 argument: router name')
        exit(1)

    get_pkt()

if __name__ == '__main__':
    main()
