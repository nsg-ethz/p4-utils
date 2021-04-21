#!/usr/bin/env python3
import argparse
import sys
import socket
import random
import struct

from scapy.all import *

intf = sys.argv[1]
def send(pckt):
    iface = "r1-eth0"
    sendp(pckt)
    print("sending on interface %s"%iface)

def get_pkt():
    load_contrib('ospf')
    sniff(iface=str(intf), prn = send)


def main():

    if len(sys.argv)<2:
        print('pass 2 arguments: <destination> "<message>"')
        exit(1)

    get_pkt()



if __name__ == '__main__':
    main()
