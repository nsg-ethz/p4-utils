from p4utils.mininetlib.network_API import NetworkAPI

net = NetworkAPI()

# Network general options
net.enableCli()
net.disableGwArp()
net.disableArpTables()
net.setLogLevel('info')

# Network definition
# Switches
net.addP4Switch('s1')
net.addP4Switch('s2')
net.addP4Switch('s3')
net.addP4Switch('s4')
net.addP4Switch('s5')
net.addP4Switch('s6')
net.setP4SourceAll('switch.p4')

# Hosts
net.addHost('h1')
net.setDefaultRoute('h1', "1.0.0.2")
net.addHost('h2')
net.setDefaultRoute('h2', "2.0.0.2")
net.addHost('h3')
net.setDefaultRoute('h3', "3.0.0.2")
net.addHost('h4')
net.setDefaultRoute('h4', '4.0.0.2')
net.addHost('h5')
net.setDefaultRoute('h5', '5.0.0.2')
net.addHost('h6')
net.setDefaultRoute('h6', '6.0.0.2')

# Routers
net.addRouter('r1', int_conf='./routers/r1.conf', bgpd=False)
net.addRouter('r2', int_conf='./routers/r2.conf', bgpd=False)
net.addRouter('r3', int_conf='./routers/r3.conf', bgpd=False)
net.addRouter('r4', int_conf='./routers/r4.conf', bgpd=False)

# Links
net.addLink('h1', 's1', bw=12)
net.setIntfIp('h1', 's1', '1.0.0.1/24')
net.setIntfMac('h1', 's1', '00:00:01:00:00:01')

net.addLink('h2', 's2', bw=12)
net.setIntfIp('h2', 's2', '2.0.0.1/24')
net.setIntfMac('h2', 's2', '00:00:02:00:00:01')

net.addLink('h3', 's3', bw=12)
net.setIntfIp('h3', 's3', '3.0.0.1/24')
net.setIntfMac('h3', 's3', '00:00:03:00:00:01')

net.addLink('h4', 's4', bw=12)
net.setIntfIp('h4', 's4', '4.0.0.1/24')
net.setIntfMac('h4', 's4', '00:00:04:00:00:01')

net.addLink('h5', 's5', bw=12)
net.setIntfIp('h5', 's5', '5.0.0.1/24')
net.setIntfMac('h5', 's5', '00:00:05:00:00:01')

net.addLink('h6', 's6', bw=12)
net.setIntfIp('h6', 's6', '6.0.0.1/24')
net.setIntfMac('h6', 's6', '00:00:06:00:00:01')

net.addLink('s1', 'r1', intfName2='port_S1', bw=6)
net.addLink('s1', 'r4', intfName2='port_S1', bw=4)
net.addLink('s1', 's6', bw=6)
net.addLink('s6', 'r1', intfName2='port_S6', bw=4)
net.addLink('s6', 'r4', intfName2='port_S6', bw=6)

net.addLink('s3', 'r2', intfName2='port_S3', bw=6)
net.addLink('s3', 'r3', intfName2='port_S3', bw=4)
net.addLink('s3', 's4', bw=6)
net.addLink('s4', 'r2', intfName2='port_S4', bw=4)
net.addLink('s4', 'r3', intfName2='port_S4', bw=6)

net.addLink('s2', 'r1', intfName2='port_S2', bw=4)
net.addLink('s2', 'r2', intfName2='port_S2', bw=4)

net.addLink('s5', 'r3', intfName2='port_S5', bw=4)
net.addLink('s5', 'r4', intfName2='port_S5', bw=4)

net.addLink('r1', 'r2', intfName1='port_R2', intfName2='port_R1', bw=4)
net.addLink('r1', 'r3', intfName1='port_R3', intfName2='port_R1', bw=6)
net.addLink('r1', 'r4', intfName1='port_R4', intfName2='port_R1', bw=4)
net.addLink('r2', 'r3', intfName1='port_R3', intfName2='port_R2', bw=4)
net.addLink('r2', 'r4', intfName1='port_R4', intfName2='port_R2', bw=6)
net.addLink('r3', 'r4', intfName1='port_R4', intfName2='port_R3', bw=4)

# Nodes general options
net.disablePcapDumpAll()
net.enableLogAll()

# Start the network
net.startNetwork()