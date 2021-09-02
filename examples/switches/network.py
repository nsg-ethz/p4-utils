from p4utils.mininetlib.network_API import NetworkAPI

net = NetworkAPI()

# Network general options
net.setLogLevel('info')
net.enableCli()

# Network definition
net.addP4Switch('s1')
net.setP4CliInput('s1', 's1-commands.txt')
net.addP4Switch('s2')
net.setP4CliInput('s2', 's2-commands.txt')
net.addP4Switch('s3')
net.setP4CliInput('s3', 's3-commands.txt')
net.setP4SourceAll('forwarding.p4')

net.addHost('h1')
net.addHost('h2')
net.addHost('h3')
net.addHost('h4')

net.addLink('h1', 's1', weight=5)
net.setBw('h1', 's1', 20)
net.setDelay('h1', 's1', 20)
net.setMaxQueueSize('h1', 's1', 100)
net.setLoss('h1', 's1', 0.01)
net.addLink('h2', 's2')
net.addLink('s1', 's2')
net.addLink('h3', 's3')
net.addLink('h4', 's3')
net.addLink('s1', 's3')

# Assignment strategy
net.mixed()

# Nodes general options
net.addTaskFile('tasks.txt')
net.enablePcapDumpAll()
net.enableLogAll()

# Start the network
net.startNetwork()