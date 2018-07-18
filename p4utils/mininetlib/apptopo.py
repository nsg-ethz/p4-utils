from mininet.topo import Topo
from mininet.nodelib import LinuxBridge
import re

class AppTopo(Topo):
    """The mininet topology class.

    A custom class is used because the exercises make a few topology assumptions,
    mostly about the IP and MAC addresses.
    """

    def __init__(self, hosts, switches, links, log_dir, global_conf, **opts):
        Topo.__init__(self, **opts)
        host_links = []
        switch_links = []
        self.sw_port_mapping = {}
        self.hosts_info = {}

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

        default_cpu_port = {'cpu_port':global_conf.get('cpu_port', False)}

        add_bridge = True
        for switch in self.switches():
            if self.g.node.get(switch).get('isP4Switch', False):
                switch_cpu_port = global_conf.get('topology', {}).get('switches', {})
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

