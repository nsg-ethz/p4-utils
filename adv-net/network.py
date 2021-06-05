import sys
import csv
from udp import *
from p4utils.mininetlib.network_API import NetworkAPI

HOSTS_TO_IP = {
    'h1': '1.0.0.1',
    'h2': '2.0.0.1',
    'h3': '3.0.0.1',
    'h4': '4.0.0.1',
    'h5': '5.0.0.1',
    'h6': '6.0.0.1'
}

def load_flows_file(config_file):
        flows = []
        with open(config_file, 'r') as csvfile:
            dialect = csv.Sniffer().sniff(csvfile.read(1024))
            csvfile.seek(0)
            reader = csv.DictReader(csvfile, dialect=dialect)
            return list(reader)

def main(config_file):
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

    net.execScript('./switches.sh')
    net.execScript('python controller.py &', reboot=True)
    net.execScript('sleep 120 && python performance.py --traffic-spec {} &'.format(config_file), reboot=True)

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
    net.addLink('h1', 's1', bw=12, intfName2='s1-host')
    net.setIntfIp('h1', 's1', HOSTS_TO_IP['h1']+'/24')
    net.setIntfMac('h1', 's1', '00:00:01:00:00:01')

    net.addLink('h2', 's2', bw=12, intfName2='s2-host')
    net.setIntfIp('h2', 's2', HOSTS_TO_IP['h2']+'/24')
    net.setIntfMac('h2', 's2', '00:00:02:00:00:01')

    net.addLink('h3', 's3', bw=12, intfName2='s3-host')
    net.setIntfIp('h3', 's3', HOSTS_TO_IP['h3']+'/24')
    net.setIntfMac('h3', 's3', '00:00:03:00:00:01')

    net.addLink('h4', 's4', bw=12, intfName2='s4-host')
    net.setIntfIp('h4', 's4', HOSTS_TO_IP['h4']+'/24')
    net.setIntfMac('h4', 's4', '00:00:04:00:00:01')

    net.addLink('h5', 's5', bw=12, intfName2='s5-host')
    net.setIntfIp('h5', 's5', HOSTS_TO_IP['h5']+'/24')
    net.setIntfMac('h5', 's5', '00:00:05:00:00:01')

    net.addLink('h6', 's6', bw=12, intfName2='s6-host')
    net.setIntfIp('h6', 's6', HOSTS_TO_IP['h6']+'/24')
    net.setIntfMac('h6', 's6', '00:00:06:00:00:01')

    net.addLink('s1', 'r1', intfName1='s1-port_R1', intfName2='port_S1', bw=6)
    net.addLink('s1', 'r4', intfName1='s1-port_R4', intfName2='port_S1', bw=4)
    net.addLink('s1', 's6', intfName1='s1-port_S6', intfName2='s6-port_S1',bw=6)
    net.addLink('s6', 'r1', intfName1='s6-port_R1', intfName2='port_S6', bw=4)
    net.addLink('s6', 'r4', intfName1='s6-port_R4', intfName2='port_S6', bw=6)

    net.addLink('s3', 'r2', intfName1='s3-port_R2', intfName2='port_S3', bw=6)
    net.addLink('s3', 'r3', intfName1='s3-port_R3', intfName2='port_S3', bw=4)
    net.addLink('s3', 's4', intfName1='s3-port_S4', intfName2='s4-port_S3', bw=6)
    net.addLink('s4', 'r2', intfName1='s4-port_R2', intfName2='port_S4', bw=4)
    net.addLink('s4', 'r3', intfName1='s4-port_R3', intfName2='port_S4', bw=6)

    net.addLink('s2', 'r1', intfName1='s2-port_R1', intfName2='port_S2', bw=4)
    net.addLink('s2', 'r2', intfName1='s2-port_R2', intfName2='port_S2', bw=4)

    net.addLink('s5', 'r3', intfName1='s5-port_R3', intfName2='port_S5', bw=4)
    net.addLink('s5', 'r4', intfName1='s5-port_R4', intfName2='port_S5', bw=4)

    net.addLink('r1', 'r2', intfName1='port_R2', intfName2='port_R1', bw=4)
    net.addLink('r1', 'r3', intfName1='port_R3', intfName2='port_R1', bw=6)
    net.addLink('r1', 'r4', intfName1='port_R4', intfName2='port_R1', bw=4)
    net.addLink('r2', 'r3', intfName1='port_R3', intfName2='port_R2', bw=4)
    net.addLink('r2', 'r4', intfName1='port_R4', intfName2='port_R2', bw=6)
    net.addLink('r3', 'r4', intfName1='port_R4', intfName2='port_R3', bw=4)

    # Nodes general options
    net.disablePcapDumpAll()
    net.enableLogAll()

    # Add tasks for traffic generation
    flows = load_flows_file(config_file)
    for kwargs in flows:
        kwargs['d'] = kwargs['duration']
        kwargs['start'] = float(kwargs['start_time'])
        kwargs['src_name'] = kwargs['src']
        kwargs['dst_name'] = kwargs['dst']
        kwargs['src'] = HOSTS_TO_IP[kwargs['src_name']]
        kwargs['dst'] = HOSTS_TO_IP[kwargs['dst_name']]
        del kwargs['duration']
        del kwargs['start_time']

        out_file = "{}/sender_{}_{}_{}_{}.txt".format(
            './flows/', kwargs['src_name'], kwargs['dst_name'], kwargs["sport"], kwargs["dport"])
        net.addTask(kwargs['src_name'], send_udp_flow, out_file=out_file, **kwargs)

        out_file = "{}/receiver_{}_{}_{}_{}.txt".format(
            './flows/', kwargs['src_name'], kwargs['dst_name'], kwargs["sport"], kwargs["dport"])
        net.addTask(kwargs['dst_name'], recv_udp_flow, src=kwargs["src"], dport=int(kwargs["dport"]), out_file=out_file)

    # Start the network
    net.startNetwork()

if __name__ == "__main__":

    main(sys.argv[1])
