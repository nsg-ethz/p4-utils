import os
from mininet.cli import CLI
from mininet.log import info, output, error, warn, debug
from p4utils.utils.utils import *
from p4utils import FAILED_STATUS, SUCCESS_STATUS

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
                warn('File Error: p4source does not exist %s\n' % p4source_path)
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
