from mininet.net import Mininet
from mininet.log import info, error, debug, output, warn
from mininet.link import Link, Intf
from p4utils.mininetlib.topo import NullLink


class P4Mininet(Mininet):
    """P4Mininet is the Mininet Class extended with P4 switches."""

    def __init__(self, *args, **kwargs):
        """Adds p4switches."""
        self.p4switches = []
        self.routers = []
        super().__init__(*args, **kwargs)

    def build(self):
        """Build P4Mininet."""
        super().build()

        for switch in self.switches:
            name = switch.name
            if self.topo.isP4Switch(name):
                self.p4switches.append(switch)

    def addRouter(self, name: str, cls=None, **params):
        """Add a router to the network
        :param name: the node name
        :param cls: the class to use to instantiate it"""

        # here we will define our params
        defaults = {}

        defaults.update(params)

        if not cls:
            cls = self.router
        r = cls(name, **defaults)
        self.routers.append(r)
        self.nameToNode[name] = r
        return r   

    def configRouters( self ):
        "Configure a set of routers"
        for router in self.routers:
            info( router.name + ' ' )
            #intf = router.defaultIntf()
            #info( intf + ' ')
            #if intf:
                #info( intf)
            
        info( '\n' )             

    def buildFromTopo( self, topo=None ):
        """Build mininet from a topology object
           At the end of this function, everything should be connected
           and up."""

        # add routers before the real mininet method is called
        info('\n*** Adding Routers:\n')
        for routerName in topo.routers():
            self.addRouter(routerName, **topo.nodeInfo(routerName))
            info(routerName + ' ')
        info('\n')

        super().buildFromTopo(topo)

    def linksBetween( self, node1, node2 ):
        "Return Links between node1 and node2 if they are not NullLinks"
        list_of_links = []

        for link in self.links:
            
            if (isinstance(link, NullLink) == False):
                
                if ( node1, node2 ) in (( link.intf1.node, link.intf2.node ),( link.intf2.node, link.intf1.node )):
                    list_of_links.append(link)
                    
        return list_of_links

    def start(self):
        super().start()

        # start routers
        info( '*** Starting %s routers\n' % len( self.routers ) )
        for router in self.routers:
            info( router.name + ' ')
            router.start()
        
        #import ipdb; ipdb.set_trace()
            
        hosts_mtu = 9500
        # Trick to allow switches to add headers
        # when packets have the max MTU
        switches_mtu = 9520

        #remove Ipv6 for all the interfaces
        for link in self.links:

            
            if isinstance(link, NullLink) == False:

                "only real links are configured here"

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

    def stop(self):

        super().stop()

        info( '*** Stopping %i routers\n' % len( self.routers ) )
        for router in self.routers:
            info( router.name + ' ' )
            router.stop()
            router.terminate()