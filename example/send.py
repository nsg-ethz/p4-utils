#!/usr/bin/env python
import sys,os
import time

#set path where the script is run
os.chdir(os.path.dirname(sys.argv[0]))
sys.path.insert(0, '../utils')

from tcp_utils import *


def main(ip, port, num_packets):

    sender = Sender()
    sender.connect(ip, port)

    try:
        while num_packets > 0:
            sender.send(" ")
            #needed so tcp does not aggregate messages
            time.sleep(0.005)
            num_packets -=1
        sender.close()

    except KeyboardInterrupt:
        sender.close()

if __name__ == '__main__':

    if len(sys.argv) != 4:
        print "Invalid number of arguments. Run as receive.py <dst_ip> <port> <packets>"

    ip = sys.argv[1]
    port = int(sys.argv[2])
    n_packets = int(sys.argv[3])

    main(ip, port, n_packets)
