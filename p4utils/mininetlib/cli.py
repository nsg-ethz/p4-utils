import os
from copy import deepcopy
from mininet.cli import CLI
from mininet.log import info, output, error, warn, debug
from p4utils.utils.helper import *


class P4CLI(CLI):

    def __init__(self, *args, **kwargs):
        self.clients = kwargs.get('clients', [])
        self.compilers = kwargs.get('compilers', [])
        self.compiler_module = kwargs.get('compiler_module', None)
        self.client_module = kwargs.get('client_module', None)
        self.scripts = kwargs.get('scripts', None)
        # Class CLI from mininet.cli does not have clients and compilers attributes
        # so they can be removed
        if 'clients' in kwargs:
            del kwargs['clients']
        if 'compilers' in kwargs:
            del kwargs['compilers']
        if 'compiler_module' in kwargs:
            del kwargs['compiler_module']
        if 'client_module' in kwargs:
            del kwargs['client_module']
        if 'scripts' in kwargs:
            del kwargs['scripts']
        super().__init__(*args, **kwargs)
        # self.mn stores the Mininet network object according to the parent object

    def getP4Switch(self, node_name):
        """
        Return the requested P4 Switch.
        
        Arguments:
            node_name (string): name of the P4 Switch
        
        Returns:
            p4switch (Mininet node object): requested node or None if no such object was found
        """
        # Check if switch is in Mininet
        if node_name not in self.mn:
            error('P4 Switch {} not found in the network.\n'.format(node_name))
            return None

        node = self.mn[node_name]

        try:
            isP4Switch = get_node_attr(node, 'isP4Switch')
            if not isP4Switch:
                error('P4 Switch {} not found in the network\n'.format(node_name))
                return None
            else:
                return node
        except AttributeError:
            error('P4 Switch {} not found in the network\n'.format(node_name))
            return None

    def do_p4switch_stop(self, line=""):
        """Stop simple switch from switch namespace."""
        switch_name = line.split()

        # Check args validity
        if not switch_name or len(switch_name) > 1:
            error('Wrong syntax.\n')
            error('usage: p4switch_stop <p4switch name>\n')
            return False

        switch_name = switch_name[0]
        p4switch = self.getP4Switch(switch_name)

        if not p4switch:
            error('usage: p4switch_stop <p4switch name>\n')
            return False
        
        p4switch.stop_p4switch()

    def do_p4switch_start(self, line=""):
        """Start again simple switch from namespace."""
        args = line.split()

        # Check args validity
        if len(args) > 5:
            error('Wrong syntax.\n')
            error('usage: p4switch_start <p4switch name> [--p4src <path>] [--cmds <path>]\n')
            return False

        switch_name = args[0]

        p4switch = self.getP4Switch(switch_name)

        if not p4switch:
            error('usage: p4switch_start <p4switch name>\n')
            return False

        # Check if switch is running
        if p4switch.switch_started():
            error('P4 Switch already running, stop it first: p4switch_stop {} \n'.format(switch_name))
            return False

        # Check if new P4 source file has been provided
        p4_src = get_node_attr(p4switch,'p4_src')
        if '--p4src' in args:
            p4_src = args[args.index('--p4src') + 1]
            # Check if file exists
            if not os.path.exists(p4_src):
                error('File Error: P4 source {} does not exist\n'.format(p4_src))
                return False
            # Check if its not a file
            if not os.path.isfile(p4_src):
                error('File Error: p4source {} is not a file\n'.format(p4_src))
                return False
        if p4_src is not None:
            compiler = get_by_attr('p4_src', os.path.realpath(p4_src), self.compilers)
            # If a compiler for the same p4_src has been found
            if compiler:
                # If new file has been provided
                if compiler.new_source():
                    debug('New p4 source file detected!\n')
                    compiler.compile()
                else:
                    debug('P4 source already compiled!\n')
            # If this file is compiled for the first time
            elif self.compiler_module is not None: 
                debug('New p4 source file detected!\n')
                compiler = self.compiler_module['class'](p4_src=p4_src,
                                                        **self.compiler_module['kwargs'])
                compiler.compile()
                self.compilers.append(compiler)
            else:
                error('No compiler module provided!')

        # Start switch
        p4switch.start()
        
        client = get_by_attr('sw_name', switch_name, self.clients)
        cmd_path = None
        # Check if new cmd file has been provided
        if '--cmds' in args:
            cmd_path = args[args.index("--cmds") + 1]
            # Check if file exists
            if not os.path.exists(cmd_path):
                error('File Error: command file {} does not exist\n'.format(cmd_path))
                return False
            # Check if its not a file
            if not os.path.isfile(cmd_path):
                error('File Error: command file {} is not a file\n'.format(cmd_path))
                return False
        # If a client is present
        if client:
            if cmd_path is not None:
                client.set_conf(cmd_path)
            # Configure switch
            try:
                client.configure()
            except FileNotFoundError:
                debug('Not configuring {}: no file found!\n'.format(switch_name))
        # If the switch has no client yet
        elif self.client_module is not None:
            try:
                thrift_port = getattr(p4switch, 'thrift_port')
            except AttributeError:
                pass
            client = self.client_module['class'](sw_name=switch_name,
                                        thrift_port=thrift_port,
                                        **self.client_module['kwargs'])
            client.set_conf(cmd_path)
            # Configure switch
            try:
                client.configure()
            except FileNotFoundError:
                debug('Not configuring {}: no file found!\n'.format(switch_name))

    def do_p4switch_reboot(self, line=""):
        """Reboot a P4 switch with a new program."""
        if not line or len(line.split()) > 5:
            error('usage: p4switch_reboot <p4switch name> [--p4src <path>] [--cmds <path>]\n')
        else:
            switch_name = line.split()[0]
            self.do_p4switch_stop(line=switch_name)
            self.do_p4switch_start(line=line)

    def do_p4switches_reboot(self, line=""):
        """
        Reboot all P4 switches with new program.

        Note:
            If you provide a P4 source code or cmd, all switches will have the same.
        """
        if len(line.split()) > 4:
            error('usage: p4switches_reboot [--p4src <path>] [--cmds <path>]\n')
        else:
            for sw in self.mn.p4switches:
                switch_name = sw.name
                self.do_p4switch_stop(line=switch_name)

                tmp_line = switch_name + " " +line
                self.do_p4switch_start(line=tmp_line)

            #run scripts
            if isinstance(self.scripts, list):
                for script in self.scripts:
                    if script["reboot_run"]:
                        info("Exec Script: {}\n".format(script["cmd"]))
                        run_command(script["cmd"])

    def do_test_p4(self, line=""):
        """Tests start stop functionalities."""
        self.do_p4switch_stop("s1")
        self.do_p4switch_start("s1")
        self.do_p4switch_reboot("s1")
        self.do_p4switches_reboot()

    def do_printSwitches(self, line=""):
        """Print names of all switches."""
        for sw in self.mn.p4switches:
            print(sw.name)

    def do_pingset(self ,line=""):
        """"""
        hosts_names = line.strip().split()
        hosts = [x for x in self.mn.hosts if x.name in hosts_names]
        self.mn.ping(hosts=hosts, timeout=1)

    # def do_printNetInfo(self, line=""):
    #     """Prints Topology Info"""

    #     self.topo = Topology(db="topology.db")
   
    #     print("\n*********************")
    #     print("Network Information:")
    #     print("*********************\n")
        
    #     switches = self.topo.get_switches()

    #     for sw in sorted(switches.keys()):
            
    #         # skip linux bridge
    #         if sw == "sw-cpu":
    #             continue

    #         thrift_port = self.topo.get_thrift_port(sw)
    #         switch_id = self.topo[sw].get("sw_id", "N/A")
    #         cpu_index = self.topo.get_cpu_port_index(sw, quiet=True)
    #         header = "{}(thirft->{}, cpu_port->{})".format(sw, thrift_port, cpu_index)

    #         header2 = "{:>4} {:>15} {:>8} {:>20} {:>16} {:>8} {:>8} {:>8} {:>8} {:>8}".format("port", "intf", "node", "mac", "ip", "bw", "weight", "delay", "loss","queue")                                                                                     

    #         print(header)
    #         print((len(header2)*"-")) 
    #         print(header2)
            
    #         for intf,port_number  in sorted(list(self.topo.get_interfaces_to_port(sw).items()), key=lambda x: x[1]):
    #             if intf == "lo":
    #                 continue
                
    #             other_node = self.topo.get_interfaces_to_node(sw)[intf]
    #             mac = self.topo[sw][other_node]['mac']
    #             ip = self.topo[sw][other_node]['ip'].split("/")[0]
    #             bw = self.topo[sw][other_node]['bw']
    #             weight = self.topo[sw][other_node]['weight']
    #             delay = self.topo[sw][other_node]['delay']
    #             loss = self.topo[sw][other_node]['loss']
    #             queue_length = self.topo[sw][other_node]['queue_length']
    #             print(("{:>4} {:>15} {:>8} {:>20} {:>16} {:>8} {:>8} {:>8} {:>8} {:>8}".format(port_number, intf, other_node, mac, ip, bw, weight, delay, loss, queue_length)))

    #         print((len(header2)*"-")) 
    #         print("")

    #     # HOST INFO
    #     print("Hosts Info")

    #     header = "{:>4} {:>15} {:>8} {:>20} {:>16} {:>8} {:>8} {:>8} {:>8} {:>8}".format(
    #         "name", "intf", "node", "mac", "ip", "bw", "weight", "delay", "loss","queue")    
        
    #     print((len(header)*"-")) 
    #     print(header)

    #     for host in sorted(self.topo.get_hosts()):           
    #         for intf,port_number  in sorted(list(self.topo.get_interfaces_to_port(host).items()), key=lambda x: x[1]):
                
    #             other_node = self.topo.get_interfaces_to_node(host)[intf]
    #             mac = self.topo[host][other_node]['mac']
    #             ip = self.topo[host][other_node]['ip'].split("/")[0]
    #             bw = self.topo[host][other_node]['bw']
    #             weight = self.topo[host][other_node]['weight']
    #             delay = self.topo[host][other_node]['delay']
    #             loss = self.topo[host][other_node]['loss']
    #             queue_length = self.topo[host][other_node]['queue_length']
    #             print(("{:>4} {:>15} {:>8} {:>20} {:>16} {:>8} {:>8} {:>8} {:>8} {:>8}".format(host, intf, other_node, mac, ip, bw, weight, delay, loss, queue_length)))

    #     print((len(header)*"-")) 
    #     print("")

#def describe(self, sw_addr=None, sw_mac=None):
#    print "**********"
#    print "Network configuration for: %s" % self.name
#    print "Default interface: %s\t%s\t%s" %(
#        self.defaultIntf().name,
#        self.defaultIntf().IP(),
#        self.defaultIntf().MAC()
#    )
#    if sw_addr is not None or sw_mac is not None:
#        print "Default route to switch: %s (%s)" % (sw_addr, sw_mac)
#    print "**********"
#    
#def describe(self):
#    print "%s -> Thrift port: %d" % (self.name, self.thrift_port)