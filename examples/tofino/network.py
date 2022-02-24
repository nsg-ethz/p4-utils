from p4utils.utils.compiler import BF_P4C
from p4utils.mininetlib.network_API import NetworkAPI

import sys

SDE = sys.argv[1]
SDE_INSTALL = SDE + "/install"

net = NetworkAPI()

# Network general options
net.setLogLevel('info')
net.enableCli()

# Tofino compiler
net.setCompiler(compilerClass=BF_P4C, sde=SDE, sde_install=SDE_INSTALL)

# Network definition
net.addTofino('s1', sde=SDE, sde_install=SDE_INSTALL)
net.addTofino('s2', sde=SDE, sde_install=SDE_INSTALL)
net.setP4SourceAll('heavy_hitter.p4')

net.addHost('h1')
net.addHost('h2')

net.addLink('h1', 's1', port2=1)
net.addLink('s1', 's2', port1=2, port2=2)
net.addLink('s2', 'h2', port1=1)

# Assignment strategy
net.l3()

# Nodes general options
net.enableLogAll()

# Start the network
net.startNetwork()
