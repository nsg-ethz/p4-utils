from p4utils.mininetlib.network_API import NetworkAPI

net = NetworkAPI()

# Network general options
net.setLogLevel('info')
net.execScript('python l2_learning_controller.py s1 digest &', reboot=True)
net.execScript('python l2_learning_controller.py s2 digest &', reboot=True)
net.execScript('python l2_learning_controller.py s3 digest &', reboot=True)

# Network definition

# Switches
# AS 1
net.addP4Switch('s1')
net.addP4Switch('s2')
# AS 2
net.addP4Switch('s3')
net.setP4SourceAll('l2_learning_digest.p4')

# Hosts
# AS 1
net.addHost('h1')
net.setDefaultRoute('h1', "1.0.0.1")
net.addHost('h4')
net.setDefaultRoute('h4', "1.0.0.1")
net.addHost('h2')
net.setDefaultRoute('h2', "1.7.0.1")
net.addHost('h5')
net.setDefaultRoute('h5', '1.7.0.1')

# AS 2
net.addHost('h3')
net.setDefaultRoute('h3', "2.0.0.1")
net.addHost('h6')
net.setDefaultRoute('h6', '2.0.0.1')

# Routers
# AS 1
net.addRouter('r1', int_conf='./routers/r1.conf', ldpd=True)
net.addRouter('r2', int_conf='./routers/r2.conf', ldpd=True)
net.addRouter('r3', int_conf='./routers/r3.conf', ldpd=True)
net.addRouter('r4', int_conf='./routers/r4.conf', ldpd=True)

# AS 2
net.addRouter('r5', int_conf='./routers/r5.conf', ldpd=True)

# Links
# AS 1
net.addLink('h1', 's1')
net.setIntfIp('h1', 's1', '1.0.0.2/24')
net.addLink('h4', 's1')
net.setIntfIp('h4', 's1', '1.0.0.3/24')
net.addLink('s1', 'r1', intfName2='port_S1')

net.addLink('h2', 's2')
net.setIntfIp('h2', 's2', '1.7.0.2/24')
net.addLink('h5', 's2')
net.setIntfIp('h5', 's2', '1.7.0.3/24')
net.addLink('s2', 'r2', intfName2='port_S2')

net.addLink('r1', 'r2', intfName1='port_R2', intfName2='port_R1')
net.addLink('r1', 'r3', intfName1='port_R3', intfName2='port_R1')
net.addLink('r1', 'r4', intfName1='port_R4', intfName2='port_R1')
net.addLink('r2', 'r3', intfName1='port_R3', intfName2='port_R2')
net.addLink('r2', 'r4', intfName1='port_R4', intfName2='port_R2')
net.addLink('r3', 'r4', intfName1='port_R4', intfName2='port_R3')

# Inter-AS
net.addLink('r4', 'r5', intfName1='port_AS2', intfName2='port_AS1')

# AS 2
net.addLink('h3', 's3')
net.setIntfIp('h3', 's3', '2.0.0.2/24')
net.addLink('h6', 's3')
net.setIntfIp('h6', 's3', '2.0.0.3/24')
net.addLink('s3', 'r5', intfName2='port_S3')

# Nodes general options
net.disableArpTables()
net.disableGwArp()
net.enablePcapDumpAll()
net.enableLogAll()
net.enableCli()
net.startNetwork()