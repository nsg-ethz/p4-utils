#!/usr/bin/env python3
import argparse
import sys
import socket
import random
import struct
from threading import *

from scapy.all import *

rtr = sys.argv[1]

# Send packet on real interface
def send(pckt):
    iface = str(rtr)+"-eth0"
    sendp(pckt, iface=iface)
    print("sending on interface %s"%iface)

# Sniff OSPF packet on fake interface 1
def get_pkt_from_fake_1():
    load_contrib('ospf')
    intf = str(rtr) + "-eth1"
    sniff(iface=str(intf), prn = send)

# Sniff OSPF packet on fake interface 2
def get_pkt_from_fake_2():
    load_contrib('ospf')
    intf = str(rtr) + "-eth2"
    sniff(iface=str(intf), prn = send)


def main():

    if len(sys.argv)<1:
        print('pass 1 argument: router name')
        exit(1)

    Thread(target = get_pkt_from_fake_1).start()
    Thread(target = get_pkt_from_fake_2).start()

if __name__ == '__main__':
    main()
