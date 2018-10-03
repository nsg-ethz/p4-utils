from mininet.topo import Topo
from mininet.nodelib import LinuxBridge
import re
from ipaddress import IPv4Network

class AppTopo(Topo):
    """The mininet topology class.

    A custom class is used because the exercises make a few topology assumptions,
    mostly about the IP and MAC addresses.
    """

    def __init__(self, hosts, switches, links, log_dir, conf, **opts):
        Topo.__init__(self, **opts)
        host_links = []
        switch_links = []
        self.sw_port_mapping = {}
        self.hosts_info = {}

        #put host as first link element
        for link in links:
            if link['node1'][0] == 'h' or link['node2'][0] == 'h':
                if link['node2'][0] == 'h':
                    #swap
                    a = link['node1']
                    b = link['node2']
                    link['node1'] = b
                    link['node2'] = a

        for link in links:
            if link['node1'][0] == 'h':
                host_links.append(link)
            else:
                switch_links.append(link)

        link_sort_key = lambda x: x['node1'] + x['node2']
        # Links must be added in a sorted order so bmv2 port numbers are predictable
        host_links.sort(key=link_sort_key)
        switch_links.sort(key=link_sort_key)

        #TODO: add jsons for each switch
        sw_id = 1

        for sw, sw_attributes in sorted(switches.items(), key=lambda x:int(re.findall(r'\d+', x[0])[-1])):
            json_file = sw_attributes["json"]
            upper_bytex = (sw_id & 0xff00) >> 8
            lower_bytex = (sw_id & 0x00ff)
            sw_ip = "10.%d.%d.254" % (upper_bytex, lower_bytex)
            self.addP4Switch(sw, log_file="%s/%s.log" % (log_dir, sw), json_path = json_file, sw_ip = sw_ip, **sw_attributes)
            sw_id +=1

        for link in host_links:
            host_name = link['node1']
            host_sw = link['node2']
            host_num = int(host_name[1:])
            sw_num = int(host_sw[1:])
            host_ip = "10.0.%d.%d" % (sw_num, host_num)
            host_mac = '00:00:00:00:%02x:%02x' % (sw_num, host_num)
            # Each host IP should be /24, so all exercise traffic will use the
            # default gateway (the switch) without sending ARP requests.
            # When hosts connected to the same switch its a problem
            #import ipdb; ipdb.set_trace()
            ops = hosts[host_name]
            self.addHost(host_name, ip=host_ip + '/24', mac=host_mac, **ops)

            self.addLink(host_name, host_sw,
                         delay=link['delay'], bw=link['bw'],
                         addr1=host_mac, addr2=host_mac, weight=link["weight"], max_queue_size=link["queue_length"])
            self.addSwitchPort(host_sw, host_name)

            self.hosts_info[host_name] = {"sw" : host_sw, "ip" : host_ip, "mac": host_mac, "mask" : 24}

        for link in switch_links:
            self.addLink(link['node1'], link['node2'],
                         delay=link['delay'], bw=link['bw'], weight=link["weight"], max_queue_size=link["queue_length"])
            self.addSwitchPort(link['node1'], link['node2'])
            self.addSwitchPort(link['node2'], link['node1'])


        #add cpu port

        default_cpu_port = {'cpu_port':conf.get('cpu_port', False)}

        add_bridge = True
        for switch in self.switches():
            if self.g.node.get(switch).get('isP4Switch', False):
                switch_cpu_port = conf.get('topology', {}).get('switches', {})
                default_cpu_port_tmp = default_cpu_port.copy()
                default_cpu_port_tmp.update(switch_cpu_port.get(switch, {}))

                if default_cpu_port_tmp.get('cpu_port', False):
                    if add_bridge:
                        sw = self.addSwitch("sw-cpu", cls=LinuxBridge, dpid='1000000000000000')
                        add_bridge = False
                    self.addLink(switch, sw, intfName1='%s-cpu-eth0' % switch, intfName2= '%s-cpu-eth1' % switch, deleteIntfs=True)
                    self.addSwitchPort(switch, sw)

        self.printPortMapping()

    def addP4Switch(self, name, **opts):
        """Add P4 switch to Mininet topology.

        Params:
            name: switch name
            opts: switch options

        Returns:
            switch name
        """
        if not opts and self.sopts:
            opts = self.sopts
        return self.addNode(name, isSwitch=True, isP4Switch=True, **opts)

    def isHiddenNode(self, node):
        """Check if node is a Hidden Node

        Params:
            node: Mininet node

        Returns:
            True if its a hidden node
        """
        return self.g.node[node].get('isHiddenNode', False)


    def isP4Switch(self, node):
        """Check if node is a P4 switch.

        Params:
            node: Mininet node

        Returns:
            True if node is a P4 switch
        """
        return self.g.node[node].get('isP4Switch', False)


    def addSwitchPort(self, sw, node2):
        if sw not in self.sw_port_mapping:
            self.sw_port_mapping[sw] = []
        portno = len(self.sw_port_mapping[sw]) + 1
        self.sw_port_mapping[sw].append((portno, node2))

    def printPortMapping(self):
        print "Switch port mapping:"
        for sw in sorted(self.sw_port_mapping.keys()):
            print "%s: " % sw,
            for portno, node2 in self.sw_port_mapping[sw]:
                print "%d:%s\t" % (portno, node2),
            print

class AppTopoStrategies(Topo):
    """The mininet topology class.

    A custom class is used because the exercises make a few topology assumptions,
    mostly about the IP and MAC addresses.
    """

    def __init__(self, hosts, switches, links, log_dir, conf, **opts):

        Topo.__init__(self, **opts)

        self._hosts = hosts
        self._switches = switches
        self._links = links
        self.log_dir = log_dir
        self.conf =  conf

        self.sw_port_mapping = {}
        self.hosts_info = {}

        self.make_topo()

    def make_topo(self):

        topology = self.conf.get('topology')
        assignment_strategy =  topology.get('assignment_strategy', None)

        if assignment_strategy == "l2":
            self.l2_assignment_strategy()

        elif assignment_strategy == "mixed":
            self.mixed_assignment_strategy()

        elif assignment_strategy == "l3":
            self.l3_assignment_strategy()

        elif assignment_strategy == "manual":
            self.manual_assignment_strategy()

        #default
        else:
            self.l2_assignment_strategy()

    def add_switches(self):

        sw_to_id = {}
        sw_id = 1
        for sw, sw_attributes in sorted(self._switches.items(), key=lambda x:int(re.findall(r'\d+', x[0])[-1])):
            json_file = sw_attributes["json"]
            upper_bytex = (sw_id & 0xff00) >> 8
            lower_bytex = (sw_id & 0x00ff)
            sw_ip = "10.%d.%d.254" % (upper_bytex, lower_bytex)
            self.addP4Switch(sw, log_file="%s/%s.log" % (self.log_dir, sw),
                             json_path = json_file, sw_ip = sw_ip, **sw_attributes)

            sw_to_id[sw] = sw_id
            sw_id +=1

        return sw_to_id

    def is_host_link(self, link):

        return link['node1'] in self._hosts or link['node2'] in self._hosts

    def get_host_position(self, link):

        return 'node1' if link['node1'] in self._hosts else 'node2'

    def get_sw_position(self, link):

        return 'node1' if link['node1'] in self._switches else 'node2'

    def ip_addres_to_mac(self, ip):

        split_ip = map(int, ip.split("."))
        mac_address = '00:%02x' + ':%02x:%02x:%02x:%02x' % tuple(split_ip)
        return mac_address

    def check_host_valid_ip_from_name(self, hosts):

        valid = True
        for host in hosts:
            if host[0] == 'h':
                try:
                    int(host[1:])
                except:
                    valid = False
            else:
                valid = False

        return valid

    def add_cpu_port(self):

        default_cpu_port = {'cpu_port':self.conf.get('cpu_port', False)}
        add_bridge = True #We use the bridge but at the same time we use the bug it has so the interfaces are not added to it, but at least we can clean easily thanks to that

        for switch in self._switches:
            if self.g.node.get(switch).get('isP4Switch', False):
                switch_cpu_port = self.conf.get('topology', {}).get('switches', {})
                default_cpu_port_tmp = default_cpu_port.copy()
                default_cpu_port_tmp.update(switch_cpu_port.get(switch, {}))

                if default_cpu_port_tmp.get('cpu_port', False):
                    if add_bridge:
                        sw = self.addSwitch("sw-cpu", cls=LinuxBridge, dpid='1000000000000000')
                        self.addSwitchPort(switch, sw)
                        add_bridge = False
                    self.addLink(switch, sw, intfName1='%s-cpu-eth0' % switch, intfName2= '%s-cpu-eth1' % switch, deleteIntfs=True)



    def l2_assignment_strategy(self):

        self.already_assigned_ips = set()
        self.add_switches()
        ip_generator = IPv4Network(unicode("10.0.0.0/16")).hosts()

        #add links and configure them: ips, macs, etc
        #assumes hosts are connected to one switch only
        for link in self._links:

            if self.is_host_link(link):
                host_name = link[self.get_host_position(link)]
                direct_sw = link[self.get_sw_position(link)]

                if self.check_host_valid_ip_from_name(self._hosts):
                    host_num = int(host_name[1:])
                    upper_byte = (host_num & 0xff00) >> 8
                    lower_byte = (host_num & 0x00ff)
                    host_ip = "10.0.%d.%d" % (upper_byte, lower_byte)

                    #we check if for some reason the ip was already given by the ip_generator. This
                    #can only happen if the host naming is not <h_x>
                    while host_ip in self.already_assigned_ips:
                        host_ip = str(next(ip_generator).compressed)
                    self.already_assigned_ips.add(host_ip)
                else:
                    host_ip = next(ip_generator).compressed
                    #we check if for some reason the ip was already given by the ip_generator. This
                    #can only happen if the host naming is not <h_x>
                    while host_ip in self.already_assigned_ips:
                        host_ip = str(next(ip_generator).compressed)
                    self.already_assigned_ips.add(host_ip)

                print host_ip

                host_mac = self.ip_addres_to_mac(host_ip) % (0)
                direct_sw_mac = self.ip_addres_to_mac(host_ip) % (1)

                ops = self._hosts[host_name]
                self.addHost(host_name, ip=host_ip+"/16", mac=host_mac, **ops)
                self.addLink(host_name, direct_sw,
                             delay=link['delay'], bw=link['bw'],
                             addr1=host_mac, addr2=direct_sw_mac, weight=link["weight"], max_queue_size=link["queue_length"])
                self.addSwitchPort(direct_sw, host_name)
                self.hosts_info[host_name] = {"sw": direct_sw, "ip": host_ip, "mac": host_mac, "mask": 24}

            #switch to switch link
            else:
                self.addLink(link['node1'], link['node2'],
                             delay=link['delay'], bw=link['bw'], weight=link["weight"],
                             max_queue_size=link["queue_length"])
                self.addSwitchPort(link['node1'], link['node2'])
                self.addSwitchPort(link['node2'], link['node1'])

        self.add_cpu_port()
        self.printPortMapping()

    def mixed_assignment_strategy(self):

        self.already_assigned_ips = set()
        sw_to_id = self.add_switches()
        sw_to_generator = {}
        #change the id to a generator for that subnet
        for sw, sw_id in sw_to_id.items():
            upper_bytex = (sw_id & 0xff00) >> 8
            lower_bytex = (sw_id & 0x00ff)
            net = "10.%d.%d.0/24" % (upper_bytex, lower_bytex)
            sw_to_generator[sw] = IPv4Network(unicode(net)).hosts()

        #add links and configure them: ips, macs, etc
        #assumes hosts are connected to one switch only
        for link in self._links:

            if self.is_host_link(link):
                host_name = link[self.get_host_position(link)]
                direct_sw = link[self.get_sw_position(link)]

                sw_id = sw_to_id[direct_sw]
                ip_generator = sw_to_generator[direct_sw]

                if self.check_host_valid_ip_from_name(self._hosts):
                    host_num = int(host_name[1:])
                    assert host_num < 254
                    upper_byte = (sw_id & 0xff00) >> 8
                    lower_byte = (sw_id & 0x00ff)
                    host_ip = "10.%d.%d.%d" % (upper_byte, lower_byte, host_num)

                    #we check if for some reason the ip was already given by the ip_generator. This
                    #can only happen if the host naming is not <h_x>
                    while host_ip in self.already_assigned_ips:
                        host_ip = str(next(ip_generator).compressed)
                    self.already_assigned_ips.add(host_ip)
                else:
                    host_ip = next(ip_generator).compressed
                    #we check if for some reason the ip was already given by the ip_generator. This
                    #can only happen if the host naming is not <h_x>
                    while host_ip in self.already_assigned_ips:
                        host_ip = str(next(ip_generator).compressed)
                    self.already_assigned_ips.add(host_ip)

                print host_ip

                host_mac = self.ip_addres_to_mac(host_ip) % (0)
                direct_sw_mac = self.ip_addres_to_mac(host_ip) % (1)

                ops = self._hosts[host_name]
                self.addHost(host_name, ip=host_ip+"/16", mac=host_mac, **ops)
                self.addLink(host_name, direct_sw,
                             delay=link['delay'], bw=link['bw'],
                             addr1=host_mac, addr2=direct_sw_mac, weight=link["weight"], max_queue_size=link["queue_length"])
                self.addSwitchPort(direct_sw, host_name)
                self.hosts_info[host_name] = {"sw": direct_sw, "ip": host_ip, "mac": host_mac, "mask": 24}

            #switch to switch link
            else:
                self.addLink(link['node1'], link['node2'],
                             delay=link['delay'], bw=link['bw'], weight=link["weight"],
                             max_queue_size=link["queue_length"])
                self.addSwitchPort(link['node1'], link['node2'])
                self.addSwitchPort(link['node2'], link['node1'])

        self.add_cpu_port()
        self.printPortMapping()

    def l3_assignment_strategy(self):
        print "Assignment Strategy L3 not implemented yet"
        exit(1)

    def manual_assignment_strategy(self):
        print "Assignment Strategy Manual not implemented yet"
        exit(1)

    def addP4Switch(self, name, **opts):
        """Add P4 switch to Mininet topology.

        Params:
            name: switch name
            opts: switch options

        Returns:
            switch name
        """
        if not opts and self.sopts:
            opts = self.sopts
        return self.addNode(name, isSwitch=True, isP4Switch=True, **opts)

    def isHiddenNode(self, node):
        """Check if node is a Hidden Node

        Params:
            node: Mininet node

        Returns:
            True if its a hidden node
        """
        return self.g.node[node].get('isHiddenNode', False)


    def isP4Switch(self, node):
        """Check if node is a P4 switch.

        Params:
            node: Mininet node

        Returns:
            True if node is a P4 switch
        """
        return self.g.node[node].get('isP4Switch', False)


    def addSwitchPort(self, sw, node2):
        if sw not in self.sw_port_mapping:
            self.sw_port_mapping[sw] = []
        portno = len(self.sw_port_mapping[sw]) + 1
        self.sw_port_mapping[sw].append((portno, node2))

    def printPortMapping(self):
        print "Switch port mapping:"
        for sw in sorted(self.sw_port_mapping.keys()):
            print "%s: " % sw,
            for portno, node2 in self.sw_port_mapping[sw]:
                print "%d:%s\t" % (portno, node2),
            print

