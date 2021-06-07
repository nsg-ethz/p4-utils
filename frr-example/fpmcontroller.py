''' Socket programming code inspired by https://pythonprogramming.net/python-binding-listening-sockets/'''
''' PyRoute2 code inspired by  https://github.com/svinota/pyroute2 '''
''' Controller code inspired by nsg.ethz.ch - p4learning'''

''' To run , use sudo python3 fpmcontroller.py <router-name> inside the router shell using mx <router-name> 
    after  the topology has run '''

import socket
import sys
from struct import *
import os
import multiprocessing
import time
import random

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
        
    # Initialization of controller for switches
    def init(self):
        self.connect_to_switches()
        self.reset_states()
        self.set_table_defaults()

    def reset_states(self):
        for controller in self.controllers.values():
            controller.table_clear("ipv4_lpm")
            controller.table_clear("ecmp_to_nhop")
        
    # Connect to fake IP based thrift port on the switches to access it
    def connect_to_switches(self):
        for p4switch in self.topo.get_p4switches():
            
            thrift_port = self.topo.get_thrift_port(p4switch)
            num = sys.argv[1]

            # Check for router namespace which matches switch, can only connect to that switch from the router namespace
            if num[1:] == p4switch[1:]:
                self.controllers[p4switch] = SimpleSwitchThriftAPI(thrift_port, thrift_ip = "{}.0.0.{}".format(str(int(p4switch[1])*15), str(1)))

    def set_table_defaults(self):
        for controller in self.controllers.values():
            controller.table_set_default("ipv4_lpm", "drop", [])


    HOSTS = ['10.0.0.1', '10.0.0.2', '10.0.0.3','22.0.0.4', '22.0.0.5', '22.0.0.6']
    PORT = 2621

    # For kernel learnt routes
    fib_for_forwarding_kernel_and_zebra = []
    # For zebra/OSPF learnt routes
    fib_for_forwarding_zebra = []
    # For multipath/addtional OSPF learnt routes
    fib_for_forwarding_zebra_multi = []

    # Final FIB with all routes
    fib_for_forwarding = []

    # Dictionary to map output ports of the switches
    port_mapping = {}

    # Create socket to bind to FPM server
    def new_socket_create(self):

        num = sys.argv[1]
        HOST = Controller.HOSTS[int(num[1])-1]
        #HOST = "127.0.0.1"
        print(HOST)

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: 
            s.bind((HOST, Controller.PORT))

        except socket.error as msg:
            print('Bind failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1])
            sys.exit()
            
        print('Socket bind complete')
        return s

    # Write table entries for switches after decoding FPM messages
    def populate_switches(self, mod, data):

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

        path = os.getcwd()
        folder = "fpm_data"
        path_save = os.path.join(path, folder)

        path_save = os.path.join(path_save, fname)
        file_name = path_save
        
        f = open(file_name,"a")
        f.write(str(msg)+"\n")
        f.close()

        

        attrs = msg['attrs']
        hdr = msg['header']
        dst_pref = msg['dst_len']

        temp_fib = []

        # Kernel route to host directly connected to switch
        if len(attrs) == 3 and isinstance(attrs[2][1], int):
            
            #Remove routes with IPs connecting the border routers as we export the AS prefix for BGP routing (for us, IP range is 25.0.1.x/24)
            if attrs[0][1][0:2] != '25':

                #Remove routes to IPv6 addresses and loopback addresses
                if attrs[0][1][5:6] == '0' and attrs[0][1][7:8] == "0":

                    # Remove routes to the control IP range for the switch control port (IP address 15.0.0.0/32, 30.0.0.0/32 etc.)
                    if int(attrs[0][1][0:2])%15 !=0:
                        temp_fib.append((dst_pref,attrs[0],attrs[2]))
        
        # Zebra OSPF multipath route for ECMP
        elif len(attrs) == 3 and attrs[2][0] == "RTA_MULTIPATH":

            #Remove routes to IPv6 addresses and loopback addresses
            if attrs[0][1][5:6] == '0' and attrs[0][1][7:8] == "0":

                temp_fib.append((dst_pref,attrs[0], ('RTA_OIF',attrs[2][1][0]['oif']), ('RTA_OIF',attrs[2][1][1]['oif'])))     

        #Zebra OSPF single route    
        elif len(attrs) == 4:

            #Remove routes to IPv6 addresses and loopback addresses
            if attrs[0][1][5:6] == '0' and attrs[0][1][7:8] == "0":
                temp_fib.append((dst_pref,attrs[0],attrs[3]))

        else:
            pass
            #print(attrs)
            #Controller.fib_for_forwarding_zebra_multi.append((attrs[0],attrs[3]))

        
        #print(temp_fib)

        intf_map_folder = "MaptoIntf"
        intf_path = os.path.join(path, intf_map_folder)
        intf_file_name = router + "intf" + ".txt"
        intf_file = os.path.join(intf_path, intf_file_name)


        with open(intf_file) as f:
            content = f.readlines()

        # Length describes the number of interfaces for the CP-router
        number_of_total_CP_interfaces = [x.strip() for x in content] 

        # We have to follow a naming convention so that the mapping always works
        # We configure our routers such that interface eth1 is always connected to the host.
        # Interfaces eth2, eth3,... are CP interfaces "connected" to other CP interfaces.
        # For the switch we have one additional real interface, which connects to the CP router (control interface) 
        # We build our topology in a way that first we add host-switch connections, then we add switch-CP router connections
        # Finally we add swich-switch connections in the same AS, followed by switch-switch connections in different AS.
        # We follow numerical ordering while building the topology, example if we have s1, s2, s3, s4
        # we first add all connections to s1 in increasing order of switch number i.e. s1-s2, then s1-s3, then s1-s4
        # then we add for s2 in increasing order, then s3, and so on
        # This naming convention ensures our controller will work for any topology.
        # We need to do this as if we randomly name interfaces on the CP routers and switches in any order, there will be no way to map actual port numbers for forwarding.

        # To check how many switches inside an AS.
        num_switches_in_AS = 3
        
        #Read the mappings generated from the files
        for item in number_of_total_CP_interfaces:
            items = item.split(",")

            #items[0] gives the interface number on the switch
                        
            # If interface is eth1, then the port number on the router and switch is the same, both = 1
            if int(items[0][-2]) == 1:
                Controller.port_mapping[int(items[1])] = int(items[0][-2])
                
            # If interface is eth2,eth3, then the port number on the switch is +1 of the router port 
            # This is because switch has an additional interface which connects to the CP router.
            # This connection is always on eth2, in the naming convention of our topology (we add the CP router link before we add switches). 
            else:
                Controller.port_mapping[int(items[1])] = int(items[0][-2]) + 1

        #print(Controller.port_mapping)

        """ 
                Key to understand :
                List of routes installed by fpm
                position in FIB list selects the route (choose by looking at the FPM routes, which route to install)
                position 0 in FIB entry selects destination prefix for the Ip address, /8 and /16 etc.
                position 1 in FIB entry selects the IP match for lookup , tuple of the form ('RTA_DST', IP)
                position 2 in FIB selects the port to forward on , tuple of the form ('RTA_OIF', PORT) 
                position 3,4,.... in FIB selects the port to forward on in case of multipath tuple of the form ('RTA_OIF', PORT)"""

        for sw_name, controller in self.controllers.items():
            
            # Check for connected switches to the given switch
            connected_switches = self.topo.get_p4switches_connected_to(sw_name)

            for host in self.topo.get_hosts_connected_to(sw_name):
                
                # Host IP from p4-utils method
                host_ip = self.topo.get_host_ip(host) + "/24"
                host_mac = self.topo.get_host_mac(host)
                
                # If there is a route in the FIB from FPM (queue is not empty)
                if temp_fib:
                
                    for entry in temp_fib:
                        
                        # Check the HOST IP from the FIB now
                        host_ip_match_from_fib = entry[1][1] + "/"+str(entry[0])

                        # Port to forward from the FIB (one of the bad interface values which needed to be mapped)
                        port_toforward_from_fib = entry[2][1]

                        # Actual port to forward traffic on
                        sw_port = Controller.port_mapping[port_toforward_from_fib]
                        print(host_ip_match_from_fib, sw_port)

                        # Check /24 prefix of the host IP to match, i.e. upto 24 bits
                        if host_ip[0:6] == host_ip_match_from_fib[0:6]:

                            print ("table_add at {}:".format(sw_name))
                            self.controllers[sw_name].table_add("ipv4_lpm", "set_nhop", [str(host_ip_match_from_fib)], [str(host_mac), str(sw_port)])

                        else:
                            #Check for multipath (no multipath for external AS routes with /8 prefix)

                            # According to the key, in every entry, postion 0 is prefix, position 1 is dst_addr
                            # position 2,3,.... are output ports (length <=3 means only one output port)
                            if len(entry) <= 3:

                                for switch in connected_switches:

                                    # Reference port from topology to map switch needed
                                    # The switch knows the port from the FPM route but not the destination MAC.
                                    # To find the destination MAC, the switch checks for which switch, the port number
                                    # matches the port given by the FPM route and finds the MAC for that switch

                                    ref_port = self.topo.node_to_node_port_num(sw_name,switch)

                                    # If port number for a connected switch, matches port to forward on
                                    if ref_port == sw_port:
                                        
                                        # Find destiantion MAC address
                                        dst_sw_mac = self.topo.node_to_node_mac(switch, sw_name)
                                        print(switch, dst_sw_mac)

                                        print ("table_add at {}:".format(sw_name))
                                        self.controllers[sw_name].table_add("ipv4_lpm", "set_nhop", [str(host_ip_match_from_fib)], [str(dst_sw_mac), str(sw_port)])

                            # Now multipath is possible, for internal AS routes only (/24 prefix)
                            elif len(entry) > 3:

                                    n_hops = len(entry) - 2

                                    # Select the /8 IP prefix as the ECMP group, as /8 prefix is different across different ASes.
                                    # This ensures ECMP works within an AS and for routes to other ASes too.
                                    ecmp_group = int(host_ip_match_from_fib[0:2])
                                    print(ecmp_group)

                                    # Populate table for ECMP 
                                    print ("table_add at {}:".format(sw_name))
                                    self.controllers[sw_name].table_add("ipv4_lpm", "ecmp_forward", [str(host_ip_match_from_fib)], [str(ecmp_group), str(n_hops)])

                                    # Extract the ouput ports from the FIB ( they occur after position 2 in the FPM route)
                                    all_hops_from_fib = [x[1] for x in entry[2:]]

                                    # Map all ports to actual forwarding ports
                                    sw_ports = [Controller.port_mapping[item] for item in all_hops_from_fib]

                                    for switch in connected_switches:
                                        
                                        # As ECMP hashes on 5 tuple modulo num_ports, index gives the value of the hash
                                        # Hash can have values from 0,1,2...num_ports-1
                                        for index, single_port in enumerate(sw_ports):

                                            ref_port = self.topo.node_to_node_port_num(sw_name,switch)

                                            if ref_port == single_port:

                                                dst_sw_mac = self.topo.node_to_node_mac(switch, sw_name)
                                                print(switch, dst_sw_mac)
                                                print(index,single_port)

                                                print ("table_add at {}:".format(sw_name))
                                                self.controllers[sw_name].table_add("ecmp_to_nhop", "set_nhop", [str(ecmp_group), str(index)], [str(dst_sw_mac), str(single_port)])


    # Parse fpm message into useful form 
    def read_fpm_message(self,data):

        #Inspired by FRR_p$ project under nsg.ethz.ch

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
                #print(tot_len)
                value = start + tot_len
                nt_msg = unpack('!' + str(tot_len-hdr_length) +'c', data[start+4:value])
                #print(nt_msg)

                nt_msg = ":".join("{:02x}".format(ord(c)) for c in nt_msg)

                path = os.getcwd()
                folder = "fpm_data"

                path_save = os.path.join(path, folder)
                
                _file = 'nt_msg'+sys.argv[1]+'.data'
                path_save = os.path.join(path_save, _file)

                file_name = path_save

                with open(file_name, 'w') as f:
                    f.write(nt_msg)

                t = self.populate_switches('pyroute2.netlink.rtnl.rtmsg.rtmsg', file_name)
                #print(t)
                start = value
                

    # Fetch the fpm message
    def get_fpm(self, conn, addr):

        with conn:
            print('Connected with ' + addr[0] + ':' + str(addr[1]))
            flag = True

            while flag:
                data = conn.recv(2048)
                self.read_fpm_message(data)

                if not data:
                    print("no data")
                    flag = False

                #return None
        
    # Contol block for fpm controller
    def main_fpm(self):

        router  = sys.argv[1]
        fname = router+"route"+".data"

        path = os.getcwd()
        folder = "fpm_data"
        path_save = os.path.join(path, folder)

        path_save = os.path.join(path_save, fname)
        file_name = path_save

        os.system("rm -f {fname}".format(fname = file_name))


        if not os.path.isdir("fpm_data"):
            os.mkdir("fpm_data")

        s = self.new_socket_create()
        s.listen()
        print("Listening....")

        conn, addr = s.accept()

        self.get_fpm(conn, addr)
        s.close()



if __name__== "__main__":
   
    controller = Controller().main_fpm()
