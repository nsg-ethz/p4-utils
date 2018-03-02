import subprocess

class AppController(object):

    def __init__(self, manifest=None, target=None, topo=None, net=None, links=None):
        self.manifest = manifest
        self.target = target
        self.conf = manifest['targets'][target]
        self.topo = topo
        self.net = net
        self.links = links

    def read_entries(self, filename):
        entries = []
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if line == '': continue
                entries.append(line)
        return entries

    def add_entries(self, thrift_port=9090, sw=None, entries=None):
        assert entries
        if sw:
            thrift_port = sw.thrift_port

        print '\n'.join(entries)
        p = subprocess.Popen(['simple_switch_CLI', '--thrift-port', str(thrift_port)], stdin=subprocess.PIPE)
        p.communicate(input='\n'.join(entries))

    def read_register(self, register, idx, thrift_port=9090, sw=None):
        if sw: thrift_port = sw.thrift_port
        p = subprocess.Popen(['simple_switch_CLI', '--thrift-port', str(thrift_port)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate(input="register_read %s %d" % (register, idx))
        reg_val = filter(lambda l: ' %s[%d]' % (register, idx) in l, stdout.split('\n'))[0].split('= ', 1)[1]
        return long(reg_val)

    def read_tables(self, thrift_port=9090):

        p = subprocess.Popen(['simple_switch_CLI', '--thrift-port', str(thrift_port)], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        stdout, stderr = p.communicate(input="show_tables")
        return stdout

    def start(self):
        #TODO: check which things found here are done in other parts in the new version
        entries = {}
        for sw in self.topo.switches():
            entries[sw] = []
            if 'switches' in self.conf and sw in self.conf['switches'] and 'entries' in self.conf['switches'][sw]:
                extra_entries = self.conf['switches'][sw]['entries']
                if type(extra_entries) == list: # array of entries
                    entries[sw] += extra_entries
                else: # path to file that contains entries
                    entries[sw] += self.read_entries(extra_entries)

        #adds arp, routes and default gateway...
        for host_name in self.topo._host_links:
            h = self.net.get(host_name)
            for link in self.topo._host_links[host_name].values():
                sw = link['sw']
                iface = h.intfNames()[link['idx']]
                # use mininet to set ip and mac to let it know the change
                h.setIP(link['host_ip'], 24)
                h.setMAC(link['host_mac'])
                h.cmd('arp -i %s -s %s %s' % (iface, link['sw_ip'], link['sw_mac']))
                h.cmd('ethtool --offload %s rx off tx off' % iface)
                h.cmd('ip route add %s dev %s' % (link['sw_ip'], iface))
            h.setDefaultRoute("via %s" % link['sw_ip'])

        print "**********"
        print "Configuring entries in p4 tables"
        for sw_name in entries:
            print
            print "Configuring switch... %s" % sw_name
            sw = self.net.get(sw_name)
            if entries[sw_name]:
                self.add_entries(sw=sw, entries=entries[sw_name])
        print "Configuration complete."
        print "**********"

    def stop(self):
        pass
