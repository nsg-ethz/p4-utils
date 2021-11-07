from p4utils.mininetlib.network_API import NetworkAPI

SDE = '/home/p4/bf-sde-9.7.0'
SDE_INSTALL = '/home/p4/bf-sde-9.7.0/install'

net = NetworkAPI()

# Network general options
net.setLogLevel('info')
net.enableCli()

# Network definition
net.addTofino('s1', p4_name='simple_l3', sde=SDE, sde_install=SDE_INSTALL)
net.addTofino('s2', p4_name='simple_l3', sde=SDE, sde_install=SDE_INSTALL)

net.addHost('h1')
net.addHost('h2')
net.addHost('h3')
net.addHost('h4')
net.addHost('h5')

net.addLink('h1', 's1')
net.addLink('h2', 's1')
net.addLink('h3', 's1')
net.addLink('h4', 's1')
net.addLink('s1', 's2')
net.addLink('s2', 'h5')

# Assignment strategy
net.l2()

# Nodes general options
#net.enablePcapDumpAll()
net.enableLogAll()

# Start the network
net.startNetwork()