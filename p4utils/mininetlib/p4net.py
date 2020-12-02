from mininet.net import Mininet

class P4Mininet(Mininet):
    """P4Mininet is the Mininet Class extended with P4 switches."""

    def __init__(self, *args, **kwargs):
        """Adds p4switches."""
        self.p4switches = []
        super(P4Mininet, self).__init__(*args, **kwargs)

    def build(self):
        """Build P4Mininet."""
        super(P4Mininet, self).build()

        for switch in self.switches:
            name = switch.name
            if self.topo.isP4Switch(name):
                self.p4switches.append(switch)


    def start(self):
        super(P4Mininet, self).start()

        hosts_mtu = 9500
        # Trick to allow switches to add headers
        # when packets have the max MTU
        switches_mtu = 9520

        #remove Ipv6 for all the interfaces
        for link in self.links:
            cmd1 = "/sbin/ethtool -k {0} rx off tx off sg off"
            cmd2 = "sysctl net.ipv6.conf.{0}.disable_ipv6=1"
            cmd3 = "ip link set {} mtu {}"

            #execute the ethtool command to remove some offloads
            link.intf1.cmd(cmd1.format(link.intf1.name))
            link.intf2.cmd(cmd1.format(link.intf2.name))

            #remove ipv6
            link.intf1.cmd(cmd2.format(link.intf1.name))
            link.intf2.cmd(cmd2.format(link.intf2.name))

            #increase mtu to 9500 (jumbo frames) for switches we do it special
            node1_is_host = link.intf1.node in self.hosts
            node2_is_host = link.intf2.node in self.hosts

            if node1_is_host or node2_is_host:
                mtu = hosts_mtu
            else:
                mtu = switches_mtu

            link.intf1.cmd(cmd3.format(link.intf1.name, mtu))
            link.intf2.cmd(cmd3.format(link.intf2.name, mtu))