from mininet.net import Mininet
from itertools import chain, groupby
from mininet.log import info, error, debug, output, warn

from p4utils.mininetlib.node import FRRouter

class P4Mininet(Mininet):
    """P4Mininet is the Mininet Class extended with P4 switches."""

    def __init__(self, *args, router=FRRouter, **kwargs):
        """Adds p4switches."""
        self.router = router
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

    def addRouter(self, name, cls=None, **params):
        """
        Add a router to the network.

        Arguments:
            name (string): name of the router to add
            cls (class)  : custom router class/constructor (optional)
        
        Returns:
            added router
        """
        defaults = {}   # Default parameters to set (maybe in the future)
        defaults.update(params)
        if not cls:
            cls = self.router
        r = cls(name, **defaults)
        self.routers.append(r)
        self.nameToNode[name] = r
        return r                

    def buildFromTopo( self, topo=None ):
        """
        Build mininet from a topology object. At the end of this 
        function, everything should be connected and up.
        """

        # Possibly we should clean up here and/or validate
        # the topo
        if self.cleanup:
            pass

        info( '*** Creating network\n' )

        if not self.controllers and self.controller:
            # Add a default controller
            info( '*** Adding controller\n' )
            classes = self.controller
            if not isinstance( classes, list ):
                classes = [ classes ]
            for i, cls in enumerate( classes ):
                # Allow Controller objects because nobody understands partial()
                if isinstance( cls, Controller ):
                    self.addController( cls )
                else:
                    self.addController( 'c%d' % i, cls )

        info( '*** Adding hosts:\n' )
        for hostName in topo.hosts():
            self.addHost( hostName, **topo.nodeInfo( hostName ) )
            info( hostName + ' ' )

        info( '\n*** Adding switches:\n' )
        for switchName in topo.switches():
            # A bit ugly: add batch parameter if appropriate
            params = topo.nodeInfo( switchName)
            cls = params.get( 'cls', self.switch )
            if hasattr( cls, 'batchStartup' ):
                params.setdefault( 'batch', True )
            self.addSwitch( switchName, **params )
            info( switchName + ' ' )

        info( '\n*** Adding routers:\n' )
        for routerName in topo.routers():
            self.addRouter( routerName, **topo.nodeInfo( routerName ))
            info( routerName + ' ')

        info( '\n*** Adding links:\n' )
        for srcName, dstName, params in topo.links(
                sort=True, withInfo=True ):
            self.addLink( **params )
            info( '(%s, %s) ' % ( srcName, dstName ) )

        info( '\n' )

    def start(self):
        super().start()

        # start routers
        info( '*** Starting %s routers\n' % len( self.routers ) )
        for router in self.routers:
            info( router.name + ' ')
            router.start()
        info( '\n' )

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

    def stop( self ):
        """Stop the controller(s), switches and hosts"""
        info( '*** Stopping %i controllers\n' % len( self.controllers ) )
        for controller in self.controllers:
            info( controller.name + ' ' )
            controller.stop()
        info( '\n' )
        if self.terms:
            info( '*** Stopping %i terms\n' % len( self.terms ) )
            self.stopXterms()
        info( '*** Stopping %i links\n' % len( self.links ) )
        for link in self.links:
            info( '.' )
            link.stop()
        info( '\n' )
        info( '*** Stopping %i routers\n' % len( self.routers ) )
        for router in self.routers:
            info( router.name + ' ' )
            router.stop()
            router.terminate()
        info('\n')
        info( '*** Stopping %i switches\n' % len( self.switches ) )
        stopped = {}
        for swclass, switches in groupby(
                sorted( self.switches,
                        key=lambda s: str( type( s ) ) ), type ):
            switches = tuple( switches )
            if hasattr( swclass, 'batchShutdown' ):
                success = swclass.batchShutdown( switches )
                stopped.update( { s: s for s in success } )
        for switch in self.switches:
            info( switch.name + ' ' )
            if switch not in stopped:
                switch.stop()
            switch.terminate()
        info( '\n' )
        info( '*** Stopping %i hosts\n' % len( self.hosts ) )
        for host in self.hosts:
            info( host.name + ' ' )
            host.terminate()
        info( '\n*** Done\n' )