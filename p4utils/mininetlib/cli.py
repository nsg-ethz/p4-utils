import os
from mininet.cli import CLI
from mininet.log import info, output, error, warn, debug
from p4utils.utils.utils import *
from p4utils import FAILED_STATUS, SUCCESS_STATUS
from p4utils.utils.topology import Topology

class P4CLI(CLI):

    def __init__(self, *args, **kwargs):
        self.conf_file = kwargs.get("conf_file", None)
        self.import_last_modifications = {}

        self.last_compilation_state = False

        if not self.conf_file:
            log.warn("No configuration given to the CLI. P4 functionalities are disabled.")
        else:
            self.config = load_conf(self.conf_file)
            # class CLI from mininet.cli does not have config parameter, thus remove it
            kwargs.__delitem__("conf_file")
        CLI.__init__(self, *args, **kwargs)

    def failed_status(self):
        self.last_compilation_state = False
        return FAILED_STATUS

    def do_load_topo_conf(self, line= ""):

        """
        Updates the topo config
        Args:
            line:

        Returns:

        """
        args = line.split()
        if args:
            conf_file = args[0]
            self.conf_file = conf_file

        #re-load conf file
        self.config = load_conf(self.conf_file)

    def do_set_p4conf(self, line=""):
        """Updates configuration file location, and reloads it."""
        args = line.split()
        conf = args[0]
        if not os.path.exists(conf):
            warn('Configuratuion file %s does not exist' % conf)
            return
        self.conf_file = conf
        self.config = load_conf(conf)

    def do_test_p4(self, line=""):
        """Tests start stop functionalities."""
        self.do_p4switch_stop("s1")
        self.do_p4switch_start("s1")
        self.do_p4switch_reboot("s1")
        self.do_p4switches_reboot()

    def do_p4switch_stop(self, line=""):
        """Stop simple switch from switch namespace."""
        switch_name = line.split()
        if not switch_name or len(switch_name) > 1:
            error('usage: p4switch_stop <p4switch name>\n')
        else:
            switch_name = switch_name[0]
            if switch_name not in self.mn:
                error("p4switch %s not in the network\n" % switch_name)
            else:
                p4switch = self.mn[switch_name]
                p4switch.stop_p4switch()

    def do_p4switch_start(self, line=""):
        """Start again simple switch from namespace."""
        args = line.split()

        # check args validity
        if len(args) > 5:
            error('usage: p4switch_start <p4switch name> [--p4src <path>] [--cmds path]\n')
            return self.failed_status()

        switch_name = args[0]

        if switch_name not in self.mn:
            error('usage: p4switch_start <p4switch name> [--p4src <path>] [--cmds path]\n')
            return self.failed_status()

        p4switch = self.mn[switch_name]

        # check if switch is running
        if p4switch.check_switch_started():
            error('P4 Switch already running, stop it first: p4switch_stop %s \n' % switch_name)
            return self.failed_status()

        #load default configuration
        # mandatory defaults if not defined we should complain
        default_p4 = self.config.get("program", None)
        default_options = self.config.get("options", None)

        # non mandatory defaults.
        default_compiler = self.config.get("compiler", DEFAULT_COMPILER)

        default_config = {"program": default_p4, "options": default_options, "compiler": default_compiler}
        #merge with switch conf
        switch_conf = default_config.copy()
        switch_conf.update(self.config['topology']['switches'][switch_name])

        if "--p4src" in args:
            p4source_path = args[args.index("--p4src")+1]
            switch_conf['program'] = p4source_path
            # check if file exists
            if not os.path.exists(p4source_path):
                warn('File Error: p4source %s does not exist\n' % p4source_path)
                return self.failed_status()
            #check if its not a file
            if not os.path.isfile(p4source_path):
                warn('File Error: p4source %s is not a file\n' % p4source_path)
                return self.failed_status()

        p4source_path_source = switch_conf['program']

        # generate output file name
        output_file = p4source_path_source.replace(".p4", "") + ".json"

        program_flag = last_modified(p4source_path_source, output_file)
        includes_flag = check_imports_last_modified(p4source_path_source,
                                                    self.import_last_modifications)

        log.debug("%s %s %s %s\n" % (p4source_path_source, output_file, program_flag, includes_flag))

        if program_flag or includes_flag or (not self.last_compilation_state):
            # compile program
            try:
                compile_p4_to_bmv2(switch_conf)
                self.last_compilation_state = True
            except CompilationError:
                log.error('Compilation failed\n')
                return self.failed_status()

            # update output program
            p4switch.json_path = output_file

        # start switch
        p4switch.start()

        # load command entries
        if "--cmds" in args:
            commands_path = args[args.index("--cmds")+1]
            # check if file exists

        else:
            commands_path = switch_conf.get('cli_input', None)

        if commands_path:
            if not os.path.exists(commands_path):
                error('File Error: commands file %s does not exist\n' % commands_path)
                return self.failed_status()
            entries = read_entries(commands_path)
            add_entries(p4switch.thrift_port, entries)

        return SUCCESS_STATUS

    def do_printSwitches(self, line=""):
        """Print names of all switches."""
        for sw in self.mn.p4switches:
            print sw.name   

    def do_p4switches_reboot(self, line=""):
        """Reboot all P4 switches with new program.

        Note:
            If you provide a P4 source code or cmd, all switches will have the same.
        """
        self.config = load_conf(self.conf_file)

        for sw in self.mn.p4switches:
            switch_name = sw.name
            self.do_p4switch_stop(line=switch_name)

            tmp_line = switch_name + " " +line
            self.do_p4switch_start(line=tmp_line)

        #run scripts
        if isinstance(self.config.get('exec_scripts', None), list):
            for script in self.config.get('exec_scripts'):
                if script["reboot_run"]:
                    info("Exec Script: {}\n".format(script["cmd"]))
                    run_command(script["cmd"])

    def do_p4switch_reboot(self, line=""):
        """Reboot a P4 switch with a new program."""
        self.config = load_conf(self.conf_file)
        if not line or len(line.split()) > 5:
            error('usage: p4switch_reboot <p4switch name> [--p4src <path>] [--cmds path]\n')
        else:
            switch_name = line.split()[0]
            self.do_p4switch_stop(line=switch_name)
            self.do_p4switch_start(line=line)

    def do_pingset(self ,line=""):
        hosts_names = line.strip().split()
        hosts = [x for x in self.mn.hosts if x.name in hosts_names]
        self.mn.ping(hosts=hosts, timeout=1)


    def do_printNetInfo(self, line=""):
        """Prints Topology Info"""

        self.topo = Topology(db="topology.db")
   
        print("\n*********************")
        print("Network Information:")
        print("*********************\n")
        
        switches = self.topo.get_switches()

        for sw in sorted(switches.keys()):
            
            # skip linux bridge
            if sw == "sw-cpu":
                continue

            thrift_port = self.topo.get_thrift_port(sw)
            switch_id = self.topo[sw].get("sw_id", "N/A")
            cpu_index = self.topo.get_cpu_port_index(sw, quiet=True)
            header = "{}(thirft->{}, cpu_port->{})".format(sw, thrift_port, cpu_index)

            header2 = "{:>4} {:>15} {:>8} {:>20} {:>16} {:>8} {:>8} {:>8} {:>8} {:>8}".format("port", "intf", "node", "mac", "ip", "bw", "weight", "delay", "loss","queue")                                                                                     

            print(header)
            print(len(header2)*"-") 
            print(header2)
            
            for intf,port_number  in sorted(self.topo.get_interfaces_to_port(sw).items(), key=lambda x: x[1]):
                if intf == "lo":
                    continue
                
                other_node = self.topo.get_interfaces_to_node(sw)[intf]
                mac = self.topo[sw][other_node]['mac']
                ip = self.topo[sw][other_node]['ip'].split("/")[0]
                bw = self.topo[sw][other_node]['bw']
                weight = self.topo[sw][other_node]['weight']
                delay = self.topo[sw][other_node]['delay']
                loss = self.topo[sw][other_node]['loss']
                queue_length = self.topo[sw][other_node]['queue_length']
                print("{:>4} {:>15} {:>8} {:>20} {:>16} {:>8} {:>8} {:>8} {:>8} {:>8}".format(port_number, intf, other_node, mac, ip, bw, weight, delay, loss, queue_length))

            print(len(header2)*"-") 
            print("")

        # HOST INFO
        print("Hosts Info")

        header = "{:>4} {:>15} {:>8} {:>20} {:>16} {:>8} {:>8} {:>8} {:>8} {:>8}".format(
            "name", "intf", "node", "mac", "ip", "bw", "weight", "delay", "loss","queue")    
        
        print(len(header)*"-") 
        print(header)

        for host in sorted(self.topo.get_hosts()):           
            for intf,port_number  in sorted(self.topo.get_interfaces_to_port(host).items(), key=lambda x: x[1]):
                
                other_node = self.topo.get_interfaces_to_node(host)[intf]
                mac = self.topo[host][other_node]['mac']
                ip = self.topo[host][other_node]['ip'].split("/")[0]
                bw = self.topo[host][other_node]['bw']
                weight = self.topo[host][other_node]['weight']
                delay = self.topo[host][other_node]['delay']
                loss = self.topo[host][other_node]['loss']
                queue_length = self.topo[host][other_node]['queue_length']
                print("{:>4} {:>15} {:>8} {:>20} {:>16} {:>8} {:>8} {:>8} {:>8} {:>8}".format(host, intf, other_node, mac, ip, bw, weight, delay, loss, queue_length))

        print(len(header)*"-") 
        print("")

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