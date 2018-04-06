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
        for sw, json_file in sorted(switches.items(), key=lambda x:int(re.findall(r'\d+', x[0])[-1])):
            upper_bytex = (sw_id & 0xff00) >> 8
            lower_bytex = (sw_id & 0x00ff)
            sw_ip = "10.%d.%d.254" % (upper_bytex, lower_bytex)
            self.addP4Switch(sw, log_file="%s/%s.log" % (log_dir, sw), json_path = json_file, sw_ip = sw_ip)
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
            if host_name == 'h2':
                self.addHost(host_name, ip=host_ip + '/24', mac=host_mac, isHiddenNode=True)
            else:
                self.addHost(host_name, ip=host_ip + '/24', mac=host_mac)
            self.addLink(host_name, host_sw,
                         delay=link['latency'], bw=link['bandwidth'],
                         addr1=host_mac, addr2=host_mac, weight=link["weight"])
            self.addSwitchPort(host_sw, host_name)

            self.hosts_info[host_name] = {"sw" : host_sw, "ip" : host_ip, "mac": host_mac, "mask" : 24}

        for link in switch_links:
            self.addLink(link['node1'], link['node2'],
                         delay=link['latency'], bw=link['bandwidth'], weight=link["weight"])
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


class AppTopo2(Topo):

    def __init__(self, links, latencies={}, manifest=None, target=None,
                 log_dir="/tmp", bws={}, **opts):
        Topo.__init__(self, **opts)

        nodes = sum(map(list, zip(*links)), [])
        host_names = sorted(list(set(filter(lambda n: n[0] == 'h', nodes))))
        sw_names = sorted(list(set(filter(lambda n: n[0] == 's', nodes))))
        sw_ports = dict([(sw, []) for sw in sw_names])

        self._host_links = {}
        self._sw_links = dict([(sw, {}) for sw in sw_names])

        #TODO: add jsons for each switch
        for sw_name in sw_names:
            self.addP4Switch(sw_name, log_file="%s/%s.log" % (log_dir, sw_name))

        for host_name in host_names:
            host_num = int(host_name[1:])

            self.addHost(host_name)

            self._host_links[host_name] = {}
            host_links = filter(lambda l: l[0] == host_name or l[1] == host_name, links)

            sw_idx = 0
            for link in host_links:
                sw = link[0] if link[0] != host_name else link[1]
                sw_num = int(sw[1:])
                assert sw[0] == 's', "Hosts should be connected to switches, not " + str(sw)
                host_ip = "10.0.%d.%d" % (sw_num, host_num)
                host_mac = '00:00:00:00:%02x:%02x' % (sw_num, host_num)
                delay_key = ''.join([host_name, sw])
                delay = latencies[delay_key] if delay_key in latencies else '0ms'
                bw = bws[delay_key] if delay_key in bws else None
                sw_ports[sw].append(host_name)
                self._host_links[host_name][sw] = dict(
                    idx=sw_idx,
                    host_mac=host_mac,
                    host_ip=host_ip,
                    sw=sw,
                    sw_mac="00:00:00:00:%02x:%02x" % (sw_num, host_num),
                    sw_ip="10.0.%d.%d" % (sw_num, 254),
                    sw_port=sw_ports[sw].index(host_name) + 1
                )
                self.addLink(host_name, sw, delay=delay, bw=bw,
                             addr1=host_mac, addr2=self._host_links[host_name][sw]['sw_mac'])
                print("Link added between: " + host_name + " " + sw)
                sw_idx += 1

        for link in links:  # only check switch-switch links
            sw1, sw2 = link
            if sw1[0] != 's' or sw2[0] != 's': continue

            delay_key = ''.join(sorted([sw1, sw2]))
            delay = latencies[delay_key] if delay_key in latencies else '0ms'
            bw = bws[delay_key] if delay_key in bws else None

            self.addLink(sw1, sw2, delay=delay, bw=bw)  # ,  max_queue_size=10)
            print("Link added between: " + sw1 + " " + sw2)

            sw_ports[sw1].append(sw2)
            sw_ports[sw2].append(sw1)

            sw1_num, sw2_num = int(sw1[1:]), int(sw2[1:])
            sw1_port = dict(mac="00:00:00:%02x:%02x:00" % (sw1_num, sw2_num), port=sw_ports[sw1].index(sw2) + 1)
            sw2_port = dict(mac="00:00:00:%02x:%02x:00" % (sw2_num, sw1_num), port=sw_ports[sw2].index(sw1) + 1)

            self._sw_links[sw1][sw2] = [sw1_port, sw2_port]
            self._sw_links[sw2][sw1] = [sw2_port, sw1_port]

    def addP4Switch(self, name, **opts):
        """Convenience method: Add P4 switch to graph.
           name: switch name
           opts: switch options
           returns: switch name"""
        if not opts and self.sopts:
            opts = self.sopts
        result = self.addNode(name, isSwitch=True, isP4Switch=True, **opts)
        return result

    def isP4Switch(self, n):
        """
        Return true if the n is a p4 switch
        :param n:
        :return:
        """
        return self.g.node[n].get('isP4Switch', False)
