from mininet.cli import CLI
from mininet.log import info, output, error
from utils import *


#TODO: Add function to compile a new p4 program
#TODO: implement start/stop functions -> add an optional new path to p4 prgram in the start function.
#TODO: for rebooted switches load their control plane, or a new one, or partial one.


class P4CLI(CLI):

    def __init__(self,*args,**kwargs):

        self.config = kwargs.get("config", None)
        if not self.config:
            log("Any configuration was given to the CLI and therefore p4 functionalities are disabled")
        else:
            #normal CLI is not  any config parameter
            kwargs.__delitem__("config")

        CLI.__init__(self,*args,**kwargs)

    def do_p4switch_stop(self,line=""):

        """stop simple switch from switch namespace"""
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

    def do_p4switch_start(self,line=""):

        #import ipdb
        #ipdb.set_trace()

        """start again simple switch from namespace"""
        args = line.split()

        #check args validity
        if len(args) > 5:
            error('usage: p4switch_start <p4switch name> [--p4source <path>] [--cmd path]\n')

        switch_name = args[0]
        if switch_name not in self.mn:
            error('usage: p4switch_start <p4switch name> [--p4source <path>] [--cmd path]\n')

        p4switch = self.mn[switch_name]

        #check if switch is running
        if p4switch.check_switch_started():
            log.warn('P4 Switch already running, stop first: p4switch_stop %s \n' % switch_name)
            return

        try:
            p4source_path = args[args.index("--p4source")+1]
            #check if file exists
            if not os.path.exists(p4source_path):
                error('File Error: p4source does not exist %s\n' % p4source_path)

        except ValueError:
            p4source_path = self.config["program"]

        #compile if needed
        output_file = p4source_path.replace(".p4", "") + ".json"
        compile_flag = last_modified(p4source_path, output_file)
        if compile_flag:
            language = self.config.get("language",None)
            if not language:
                language = "p4-16"
            compile_config = {"language": language, "program_file": p4source_path}
            #compile program
            compile_p4_to_bmv2(compile_config)
            #update output program
            p4switch.json_path = output_file

        #start switch
        p4switch.start_p4switch()

        #load command entries
        try:
            commands_path = args[args.index("--cmd")+1]
            #check if file exists
            if not os.path.exists(commands_path):
                error('File Error: commands does not exist %s\n' % commands_path)
        except ValueError:
            #TODO: support different configuration files
            commands_path= self.config["targets"]["multiswitch"]["switches"][switch_name]["entries"]

        entries = read_entries(commands_path)

        #add entries
        add_entries(p4switch.thrift_port, entries)


    def do_p4switches_reboot(self, line=""):
        """reboot all p4 switches with new program """
        #TODO: only p4 switches, to do that i would have to modify topology class and do like we do with routers
        for sw in self.mn.switches:
            switch_name = sw.name
            self.do_p4switch_stop(line=switch_name)

            line = switch_name + " " +line
            self.do_p4switch_start(line=line)


    def do_p4switch_reboot(self,line=""):

        """reboot a p4 switch with new program"""
        switch_name = line.split()[0]

        self.do_p4switch_stop(line=switch_name)
        self.do_p4switch_start(line=line)
