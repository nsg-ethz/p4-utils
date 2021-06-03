'''Socket programming code inspired by https://pythonprogramming.net/python-binding-listening-sockets/'''
'''PyRoute2 code inspired by  https://github.com/svinota/pyroute2 '''
''' Controller code inspired by nsg.eth.ch - p4learning'''

''' To run , use sudo python3 get_fpm.py <router-name> inside the router shell using mx <router-name> 
    after  sudo python3 run_network.py -t <topology-name> '''

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
        self.main_fpm()
        #self.set_table_entries()
        
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
            if num[1] == p4switch[1]:
                self.controllers[p4switch] = SimpleSwitchThriftAPI(thrift_port, thrift_ip = "{}.0.0.{}".format(str(int(p4switch[1])*15), str(1)))

    def set_table_defaults(self):
        for controller in self.controllers.values():
            controller.table_set_default("ipv4_lpm", "drop", [])

    # Still a little meta, need to make it more generic
    def set_table_entries(self):

        # get the FPM data for the Forwarding Information Base
        fib = self.main_fpm()
        #print(*fib, sep = "\n")
        external_connected_switches = [] 

        for sw_name, controller in self.controllers.items():

            for host in self.topo.get_hosts_connected_to(sw_name):

                host_ip = self.topo.get_host_ip(host) + "/24"
                host_mac = self.topo.get_host_mac(host)

                """ 
                Key to understand :
                List of routes installed by fpm
                position in FIB list selects the route (choose by looking at the FPM routes, which route to install)
                position 0 in FIB entry selects destination prefix for the Ip address, /8 and /16 etc.
                position 1 in FIB entry selects the IP match for lookup , tuple of the form ('RTA_DST', IP)
                position 2 in FIB selects the port to forward on , tuple of the form ('RTA_OIF', PORT) 
                position 3,4,.... in FIB selects the port to forward on in case of multipath tuple of the form ('RTA_OIF', PORT)"""

                """So for entry in fib, entry[0] is dst_prefix, entry[1][1] is host IP for forwarding
                entry[2:][1] are the output interfaces for forwarding """

                # Connection to directly connected host (always OIF with the biggest PID)

                all_OIF = [x[2] for x in fib]
                #print(all_OIF)
                sorted_OIF = sorted([z[1] for z in all_OIF])
                unique_sorted_OIF = sorted(list(set(sorted_OIF)))
                max_OIF = max(sorted_OIF)
                max_SECOND_OIF = max(unique_sorted_OIF[0:len(unique_sorted_OIF)-1])

                # All connected switches
                connected_switches = self.topo.get_p4switches_connected_to(sw_name)
                
                # Switches connected which are in the other AS
                for switch in connected_switches:
                    if switch.endswith('2') or switch.endswith('4'):
                        external_connected_switches.append(switch)
                
                # Only routes to the end hosts are needed for the swtiches, intermediate routes from OSPF are not needed.
                _fib = []
                _fib.append(fib[0])
                _fib.extend(fib[4:])

                #print(*_fib, sep = "\n")

                for entry in _fib:

                    # For non border AS switches, execute this part. This is needed as the border switches have different 
                    # FIBS compared to the interior AS switches.

                    if not (sw_name[1:]=='2' or sw_name[1:]=='4'):
                        
                        if entry[2][1] == max_OIF:

                            # Directly connected host to the switch
                            host_ip_match_from_fib = entry[1][1] + "/"+str(entry[0])
                            print(host_ip_match_from_fib)
                            port_toforward_from_fib = entry[2][1]
                    
                            # Need to match interface as PID number to real port

                            # Port 1 (with biggest PID always) is always connected to the host, port 3 to CP router, port 100,101.. from CP fake interfaces, other ports to switches
                            sw_port = self.topo.node_to_node_port_num(sw_name, host)
                    
                            print(sw_port)

                            print ("table_add at {}:".format(sw_name))
                            self.controllers[sw_name].table_add("ipv4_lpm", "set_nhop", [str(host_ip_match_from_fib)], [str(host_mac), str(sw_port)])

                        # Single path only, no ECMP in that case
                        elif (entry[2][1] != max_OIF and len(entry) <= 3) or entry[0]==8:

                            # Other hosts and switches in the network as destination, not hosts directly
                            host_ip_match_from_fib = entry[1][1] + "/"+str(entry[0])    
                            print(host_ip_match_from_fib)

                            port_toforward_from_fib = entry[2][1] 

                            # Need to match interface as PID number to real port
                            if port_toforward_from_fib == unique_sorted_OIF[1]:
                                dst_sw_mac = self.topo.node_to_node_mac(connected_switches[0], sw_name)
                                sw_port = self.topo.node_to_node_port_num(sw_name, connected_switches[0])
                                print(sw_port)
                                print ("table_add at {}:".format(sw_name))
                                self.controllers[sw_name].table_add("ipv4_lpm", "set_nhop", [str(host_ip_match_from_fib)], [str(dst_sw_mac), str(sw_port)])

                            elif port_toforward_from_fib == unique_sorted_OIF[2]:
                                dst_sw_mac = self.topo.node_to_node_mac(connected_switches[1], sw_name)
                                sw_port = self.topo.node_to_node_port_num(sw_name, connected_switches[1])
                                print(sw_port)
                                print ("table_add at {}:".format(sw_name))
                                self.controllers[sw_name].table_add("ipv4_lpm", "set_nhop", [str(host_ip_match_from_fib)], [str(dst_sw_mac), str(sw_port)])

                        # Multiple ECMP paths as calculated by FRR, OIFs generated by the OSPF
                        # 3 because in every entry position 0 is prefix length, position 1 is IP, position 2,2,3,... are hops
                        elif len(entry) > 3 and entry[0]!=8:
                            #n_hops is number of values in entry - 2, as after position 0 and 1, everything is hops.
                            n_hops = len(entry) - 2

                            host_ip_match_from_fib = entry[1][1] + "/"+str(entry[0])
                            print(host_ip_match_from_fib)

                            ecmp_group = int(host_ip_match_from_fib[0:2])

                            print ("table_add at {}:".format(sw_name))
                            self.controllers[sw_name].table_add("ipv4_lpm", "ecmp_forward", [str(host_ip_match_from_fib)], [str(n_hops)])

                            for index, value in enumerate(entry):
                                
                                # Index 0 refers to the dstLen prefix, index 1 is IP mapping, index 2,3,.. are n_hops
                                if index == 0:
                                    continue
                                if index == 1:
                                    continue

                                # Index values upto < num of the hops is valid values for ECMP hash.
                                # Index values are modulo num_hops, must be less than num_hops
                                # Index -2 gives the correct value, as first two positions in entry are not next hops

                                port_toforward_from_fib = entry[index][1] 

                                
                                if port_toforward_from_fib == unique_sorted_OIF[1]:
                                    dst_sw_mac = self.topo.node_to_node_mac(connected_switches[0], sw_name)
                                    sw_port = self.topo.node_to_node_port_num(sw_name, connected_switches[0])
                                    #print(index-2)
                                    print(sw_port)
                                    print ("table_add at {}:".format(sw_name))
                                    self.controllers[sw_name].table_add("ecmp_to_nhop", "set_nhop", [str(index - 2)], [str(dst_sw_mac), str(sw_port)])
                                    
                                elif port_toforward_from_fib == unique_sorted_OIF[2]:
                                    dst_sw_mac = self.topo.node_to_node_mac(connected_switches[1], sw_name)
                                    sw_port = self.topo.node_to_node_port_num(sw_name, connected_switches[1])
                                    #print(index-2)
                                    print(sw_port)
                                    print ("table_add at {}:".format(sw_name))
                                    self.controllers[sw_name].table_add("ecmp_to_nhop", "set_nhop", [str(index - 2)], [str(dst_sw_mac), str(sw_port)])
                
                ext_fib = []
                ext_fib.append(fib[0])
                ext_fib.extend(fib[4:])

                for entry in ext_fib:
                    if entry[1][1][0:2]=="25":
                        ext_fib.remove(entry)
                    if entry[1][1][5:6]=="6":
                        ext_fib.remove(entry)

                print(*ext_fib, sep = "\n")

                for entry in ext_fib:

                    if (sw_name[1:]=='2' or sw_name[1:]=='4'):


                    # For border AS switches, FIBs are a little different   
                    # They have new routes which map to other ASes, and they have more interfaces.
                    #else:

                        # Need to differentaite between switches inside the AS and switches outside the AS.
                        # This is needed to prevent sending packets internal to the AS outside the AS.
                        internal_connected_switches = sorted(list(set(connected_switches)-set(external_connected_switches)))
                        #print(internal_connected_switches)

                        # Here max PID is connected to other AS, second max PID to direct host, rest is the same.
                        if entry[2][1] == max_OIF:

                            host_ip_match_from_fib = entry[1][1] + "/"+str(entry[0])
                            print(host_ip_match_from_fib)
                            port_toforward_from_fib = entry[2][1]

                            sw_port = self.topo.node_to_node_port_num(sw_name, external_connected_switches[0])

                            print(sw_port)
                            self.controllers[sw_name].table_add("ipv4_lpm", "set_nhop", [str(host_ip_match_from_fib)], [str(host_mac), str(sw_port)])

                        # Directly connected host to the switch
                        elif entry[2][1] == max_SECOND_OIF:
                            
                            host_ip_match_from_fib = entry[1][1] + "/"+str(entry[0])
                            print(host_ip_match_from_fib)
                            port_toforward_from_fib = entry[2][1]

                            # port connected to host directly
                            sw_port = self.topo.node_to_node_port_num(sw_name, host)
                    
                            print(sw_port)

                            print ("table_add at {}:".format(sw_name))
                            self.controllers[sw_name].table_add("ipv4_lpm", "set_nhop", [str(host_ip_match_from_fib)], [str(host_mac), str(sw_port)])

                        elif ((entry[2][1] != max_OIF and entry[2][1] != max_SECOND_OIF) and len(entry) <=3) or entry[0]==8:

                            # Other hosts and switches in the network as destination, not hosts directly
                            host_ip_match_from_fib = entry[1][1] + "/"+str(entry[0])
                            print(host_ip_match_from_fib)
                            port_toforward_from_fib = entry[2][1] 

                            # Need to match interface as PID number to real port
                            if port_toforward_from_fib == unique_sorted_OIF[1]:
                                dst_sw_mac = self.topo.node_to_node_mac(internal_connected_switches[0], sw_name)
                                sw_port = self.topo.node_to_node_port_num(sw_name, internal_connected_switches[0])
                                print(sw_port)
                                print ("table_add at {}:".format(sw_name))
                                self.controllers[sw_name].table_add("ipv4_lpm", "set_nhop", [str(host_ip_match_from_fib)], [str(dst_sw_mac), str(sw_port)])

                            elif port_toforward_from_fib == unique_sorted_OIF[2]:
                                dst_sw_mac = self.topo.node_to_node_mac(internal_connected_switches[1], sw_name)
                                sw_port = self.topo.node_to_node_port_num(sw_name, internal_connected_switches[1])
                                print(sw_port)
                                print ("table_add at {}:".format(sw_name))
                                self.controllers[sw_name].table_add("ipv4_lpm", "set_nhop", [str(host_ip_match_from_fib)], [str(dst_sw_mac), str(sw_port)])


                        # Multiple ECMP paths as calculated by FRR, OIFs generated by the OSPF,BGP..
                        # 3 because in every entry position 0 is prefix length, position 1 is IP, position 2,2,3,... are hops
                        elif len(entry) > 3 and entry[0]!=8:

                            n_hops = len(entry) - 2
                            host_ip_match_from_fib = entry[1][1] + "/"+str(entry[0])
                            print(host_ip_match_from_fib)

                            ecmp_group = int(host_ip_match_from_fib[0:2])
                            print(ecmp_group)

                            print ("table_add at {}:".format(sw_name))
                            self.controllers[sw_name].table_add("ipv4_lpm", "ecmp_forward", [str(host_ip_match_from_fib)], [str(n_hops)])

                            for index, value in enumerate(entry):
                                
                                # Index 0 refers to the connection to the host
                                if index == 0:
                                    continue
                                if index == 1:
                                    continue

                                # Index values upto < num of the hops is valid values for ECMP hash.
                                # Index values are modulo num_hops, must be less than num_hops
                                # Index -2 gives the correct value, as first two positions in entry are not next hops

                                port_toforward_from_fib = entry[index][1] 

                                
                                if port_toforward_from_fib == unique_sorted_OIF[1]:
                                    dst_sw_mac = self.topo.node_to_node_mac(internal_connected_switches[0], sw_name)
                                    sw_port = self.topo.node_to_node_port_num(sw_name, internal_connected_switches[0])
                                    print(index-2)
                                    print(sw_port)
                                    print ("table_add at {}:".format(sw_name))
                                    self.controllers[sw_name].table_add("ecmp_to_nhop", "set_nhop", [str(index - 2)], [str(dst_sw_mac), str(sw_port)])
                                    
                                elif port_toforward_from_fib == unique_sorted_OIF[2]:
                                    dst_sw_mac = self.topo.node_to_node_mac(internal_connected_switches[1], sw_name)
                                    sw_port = self.topo.node_to_node_port_num(sw_name, internal_connected_switches[1])
                                    print(index-2)
                                    print(sw_port)
                                    print ("table_add at {}:".format(sw_name))
                                    self.controllers[sw_name].table_add("ecmp_to_nhop", "set_nhop", [str(index - 2)], [str(dst_sw_mac), str(sw_port)])



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

    # Decoder to write fpm message
    def decoder(self, mod, data):

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
            Controller.fib_for_forwarding_kernel_and_zebra.append((dst_pref,attrs[0],attrs[2]))

            #Remove routes with IPs connecting the border routers as we export the AS prefix for BGP routing
            if attrs[0][1][0:2] != '25':

                #Remove routes to IPv6 addresses and loopback addresses
                if attrs[0][1][5:6] == '0' and attrs[0][1][7:8] == "0":

                    # Remove routes to the control IP range for the switch control port (IP address 15.0.0.0/32, 30.0.0.0/32 etc.)
                    if int(attrs[0][1][0:2])%15 !=0:
                        temp_fib.append((dst_pref,attrs[0],attrs[2]))
        
        # Zebra OSPF multipath route for ECMP
        elif len(attrs) == 3 and attrs[2][0] == "RTA_MULTIPATH":
            Controller.fib_for_forwarding_zebra_multi.append((dst_pref,attrs[0], ('RTA_OIF',attrs[2][1][0]['oif']), ('RTA_OIF',attrs[2][1][1]['oif'])))
            temp_fib.append((dst_pref,attrs[0], ('RTA_OIF',attrs[2][1][0]['oif']), ('RTA_OIF',attrs[2][1][1]['oif'])))     

        #Zebra OSPF single route    
        elif len(attrs) == 4:
            Controller.fib_for_forwarding_kernel_and_zebra.append((dst_pref,attrs[0],attrs[3]))
            if attrs[0][1][5:6] == '0':
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
        # We do this by first defining all interfaces which conenct to switches inside the AS.
        # These interfaces will have the same port number for the p4 switch and CP router interfaces.
        # Only problem is switches which connect to other AS.
        # For that, we skip one port number as after all ports are defined within an AS
        # The next port connects to the CP router (the real link)
        # All ports after that connect to other ASes, so we add +1 to the port number.
        # We define out topology this way too, first connection to hosts, then connection to
        # switches in the same AS, then connection to CP routers, then connection to other AS.
        # It works for any topology, just the order in which we add should be fixed, else it becomes 
        # extremely random and it will not work universally.

        # To check how many switches inside an AS.
        num_switches_in_AS = 3
        
        #Read the mappings generated from the files
        for item in number_of_total_CP_interfaces:
            items = item.split(",")
            #print(items[0],items[1], items[0][-2], int(items[1]))
                        
            # If lenth > num_switches, means it is a switch which connects to another AS.
            # Check if interface number exceeds  the number of switches inside the AS.
            # For those interfaces only, add +1 as we need to skip one port.
            if int(items[0][-2]) >= len(number_of_total_CP_interfaces) and len(number_of_total_CP_interfaces) > num_switches_in_AS:
                Controller.port_mapping[int(items[1])] = int(items[0][-2]) + 1
            else:
                Controller.port_mapping[int(items[1])] = int(items[0][-2])

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

            connected_switches = self.topo.get_p4switches_connected_to(sw_name)

            for host in self.topo.get_hosts_connected_to(sw_name):

                host_ip = self.topo.get_host_ip(host) + "/24"
                host_mac = self.topo.get_host_mac(host)
                
                # If there is a route in the FIB from FPM
                if temp_fib:
                
                    for entry in temp_fib:
                        
                        host_ip_match_from_fib = entry[1][1] + "/"+str(entry[0])

                        port_toforward_from_fib = entry[2][1]
                        #print(host_ip_match_from_fib, port_toforward_from_fib)

                        sw_port = Controller.port_mapping[port_toforward_from_fib]
                        print(host_ip_match_from_fib, sw_port)

                        # Check /24 prefix of the host IP to match, i.e. upto 24 bits
                        if host_ip[0:6] == host_ip_match_from_fib[0:6]:

                            print ("table_add at {}:".format(sw_name))
                            self.controllers[sw_name].table_add("ipv4_lpm", "set_nhop", [str(host_ip_match_from_fib)], [str(host_mac), str(sw_port)])

                        else:

                            for switch in connected_switches:
                            
                                if len(entry) <= 4 or entry[0]==8:

                                

                                    # Reference port from topology to map switch needed
                                    # The switch knows the port from the FPM route but not the destination MAC.
                                    # To find the destination MAC, the switch checks  for which switch, the port number
                                    # matches the port given by the FPM route and finds the MAC for that switch

                                    ref_port = self.topo.node_to_node_port_num(sw_name,switch)
                
                                    if ref_port == sw_port:

                                        dst_sw_mac = self.topo.node_to_node_mac(switch, sw_name)
                                        print(switch, dst_sw_mac)

                                        print ("table_add at {}:".format(sw_name))
                                        self.controllers[sw_name].table_add("ipv4_lpm", "set_nhop", [str(host_ip_match_from_fib)], [str(dst_sw_mac), str(sw_port)])
                            
                                elif len(entry) > 10:

                                    n_hops = len(entry) - 2

                                    print ("table_add at {}:".format(sw_name))
                                    self.controllers[sw_name].table_add("ipv4_lpm", "ecmp_forward", [str(host_ip_match_from_fib)], [str(n_hops)])

                                    all_hops = entry[2:]
                                    all_hops_from_fib = [x[1] for x in all_hops]

                                    sw_ports = [Controller.port_mapping[item] for item in all_hops_from_fib]

                                    for index, single_port in enumerate(sw_ports):

                                        ref_port = self.topo.node_to_node_port_num(sw_name,switch)
                                        #print(index, switch, ref_port)

                                        if ref_port == single_port:

                                            dst_sw_mac = self.topo.node_to_node_mac(switch, sw_name)
                                            print(switch, dst_sw_mac)
                                            print(index,single_port)

                                            print ("table_add at {}:".format(sw_name))
                                            self.controllers[sw_name].table_add("ecmp_to_nhop", "set_nhop", [str(index)], [str(dst_sw_mac), str(single_port)])


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

                t = self.decoder('pyroute2.netlink.rtnl.rtmsg.rtmsg', file_name)
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
        
    # Contol block for fpm code
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

        for item in Controller.fib_for_forwarding_kernel_and_zebra:
            Controller.fib_for_forwarding.append(item)
        
        Controller.fib_for_forwarding.pop()
        Controller.fib_for_forwarding.pop()

        for item in Controller.fib_for_forwarding_zebra_multi:
            Controller.fib_for_forwarding.append(item)

        '''for item in Controller.fib_for_forwarding_zebra:
            Controller.fib_for_forwarding.append(item)'''

        print()

        return Controller.fib_for_forwarding


if __name__== "__main__":
   
    controller = Controller()
