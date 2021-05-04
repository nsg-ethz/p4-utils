'''Socket programming code inspired by https://pythonprogramming.net/python-binding-listening-sockets/'''
'''PyRoute2 code inspired by  https://github.com/svinota/pyroute2 '''

''' To run , use sudo python3 get_fpm.py <router-name> inside the router shell using mx <router-name> 
    after  sudo python3 run_network.py -t <topology-name> '''

import socket
import sys
from struct import *
import os
import multiprocessing

from importlib import import_module
from pyroute2.common import load_dump
from pyroute2.common import hexdump

from p4utils.utils.topology import NetworkGraph
from p4utils.utils.helper import load_topo
from p4utils.utils.sswitch_thrift_API import SimpleSwitchThriftAPI

class Controller(object):

    def __init__(self):

        self.topo = load_topo('topology.json')
        self.controllers = {}
        self.init()

    def init(self):
        self.connect_to_switches()
        self.reset_states()
        self.set_table_defaults()
        self.set_table_entries()

    
    def reset_states(self):
        [controller.reset_state() for controller in self.controllers.values()]

    def connect_to_switches(self):
        for p4switch in self.topo.get_p4switches():
            
            thrift_port = self.topo.get_thrift_port(p4switch)
            num = sys.argv[1]

            # Check for router namespace which matches switch
            if num[1] == p4switch[1]:
                self.controllers[p4switch] = SimpleSwitchThriftAPI(thrift_port, thrift_ip = "{}.0.0.{}".format(str(int(p4switch[1])*15), str(1)))

    def set_table_defaults(self):
        for controller in self.controllers.values():
            pass
            #controller.table_set_default("ipv4_lpm", "NoAction", [])

    def set_table_entries(self):
        pass
    

HOSTS = ['10.0.0.1', '10.0.0.2']
PORT = 2621


def new_socket_create():

    num = sys.argv[1]
    HOST = HOSTS[int(num[1])-1]
    print(HOST)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try: 
        s.bind((HOST, PORT))

    except socket.error as msg:
        print('Bind failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1])
        sys.exit()
        
    print('Socket bind complete')
    return s

def decoder(mod, data):

    s = mod.split('.')
    package = '.'.join(s[:-1])
    module = s[-1]
    #print(package, module)
    m = import_module(package)
    met = getattr(m, module)
    #print(met)
    f = open(data, 'r')
    data = load_dump(f) 

    offset = 0
    inbox = []
    msg = met(data[offset:])
    msg.decode()


    router  = sys.argv[1]
    fname = router+"route"+".data"
    
    f = open(fname,"a")
    f.write(str(msg["attrs"])+"\n")
    f.close()

    #print(msg)
    attrs = msg['attrs']
    hdr = msg['header']
    print(msg)



def read_fpm_message(data):

    #Inspired by FRR_p$ project under nsg.ethhz.ch

    ''' Start reading the messages after the verion (1 byte) and protocol = {1 : netlink, 2 : protobuf} (1 byte)
    msg length = 2 bytes

    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +---------------+---------------+-------------------------------+
    | Version       | Message type  | Message length                |
    +---------------+---------------+-------------------------------+
    | Data...                                                       |
    +---------------------------------------------------------------+

    unpack every 2 bytes and parse it
    '''

    start = 0
    hdr_length = 4 

    value = 0

    while value < len(data):

        version = data[start]
        protocol = data[start+1]

        if version != 1: 
            print(("incorrect version", version))

        if protocol != 1:
            print(("netlink not found, instead = ", protocol))
        else:
            tot_len = unpack('!H', data[start+2:start+4])[0]
            print(tot_len)
            value = start + tot_len
            nt_msg = unpack('!' + str(tot_len-hdr_length) +'c', data[start+4:value])
            #print(nt_msg)

            nt_msg = ":".join("{:02x}".format(ord(c)) for c in nt_msg)
            file_name = 'nt_msg'+sys.argv[1]+'.data'
            with open(file_name, 'w') as f:
                f.write(nt_msg)
            #print(nt_msg)
           # print(value)

            t = decoder('pyroute2.netlink.rtnl.rtmsg.rtmsg', file_name)
            #print(t)
            start = value
            


def get_fpm(conn, addr):

    with conn:
        print('Connected with ' + addr[0] + ':' + str(addr[1]))
        flag = True
        while flag:
            data = conn.recv(2048)
            read_fpm_message(data)
            return None
            if not data:
                print("no data")
                flag = False
                conn.close()
            
                #conn.sendall(data)
    

def main():

    router  = sys.argv[1]
    fname = router+"route"+".data"

    os.system("rm -f {fname}".format(fname = fname))

    s = new_socket_create()
    s.listen()
    print("Listening....")

    conn, addr = s.accept()

    get_fpm(conn, addr)
    s.close()



if __name__== "__main__":
    main()
    controller = Controller()
