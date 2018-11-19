from __future__ import print_function
import sys, os
import subprocess
import json
from mininet import log
import mininet.clean

from p4utils import DEFAULT_COMPILER, DEFAULT_CLI

import psutil

def cleanup():
    mininet.clean.cleanup()
    bridges = mininet.clean.sh("brctl show | awk 'FNR > 1 {print $1}'").splitlines()
    for bridge in bridges:
        mininet.clean.sh("ifconfig %s down" %bridge)
        mininet.clean.sh("brctl delbr %s" % bridge)

def check_listening_on_port(port):
    for c in psutil.net_connections(kind='inet'):
        if c.status == 'LISTEN' and c.laddr[1] == port:
            return True
    return False

class CompilationError(Exception):
    pass

def last_modified(input_file, output_file):
    """Check if a file is newer than another file.

    Params:
        input_file: input file
        output_file: output file

    Returns:
        True if input_file is newer than output_file or if output_file does not exist
    """
    if not os.path.exists(input_file):
        log.error("input file does not exist")

    if not os.path.exists(output_file):
        return True

    return os.path.getmtime(input_file) > os.path.getmtime(output_file)

def get_imported_files(input_file):
    includes = []

    with open(input_file, "r") as f:
        lines = f.readlines()

    for line in lines:
        tmp = line.strip()
        if tmp.startswith("#include"):
            file_name = tmp.split(" ")[1]

            # find if it is surrounded by <>
            if  not (file_name.startswith("<") and file_name.endswith(">")):
                includes.append(file_name.strip('"'))

    return includes

def check_imports_last_modified(input_file, import_last_modifications):
    """Check if imports/includes in main P4 program have been modified.

    Args:
        input_file: path to main P4 file
        import_last_modifications: dict where time of last modification of each P4 file is saved
    """
    previous_path = os.getcwd()
    imported_files = get_imported_files(input_file)
    #move to the main file path so we check input files relative to that
    dst_dir = os.path.dirname(input_file)
    if not dst_dir:
        dst_dir = "./"
    os.chdir(dst_dir)
    compile_flag = False
    for import_file in imported_files:

        if not os.path.exists(import_file):
            log.error("File %s does not exist \n" % import_file)

            os.chdir(previous_path)
            raise IOError

        # add if they are bigger or not.
        last_time = os.path.getmtime(import_file)
        if last_time > import_last_modifications.get(import_file, 0):
            import_last_modifications[import_file] = last_time
            compile_flag = True

    os.chdir(previous_path)
    return compile_flag

def load_conf(conf_file):
    with open(conf_file, 'r') as f:
        config = json.load(f)
    return config

def log_error(*items):
    print(*items, file=sys.stderr)

def run_command(command):
    log.debug(command)
    return os.WEXITSTATUS(os.system(command))

def read_entries(filename):
    #read entries and remove empty lines
    with open(filename, "r") as f:
        entries = [x.strip() for x in f.readlines() if x.strip() != ""]
    return entries

def compile_p4_to_bmv2(config):
    """Compile P4 program to JSON file that can be loaded by bmv2.

    Args:
        config: dictionary with info about P4 version and P4 file to compile

    Returns:
        Compiled P4 program as a JSON file

    Raises:
        CompilationError: if compilation is not successful
    """
    compiler_args = []

    #read compiler to use
    compiler = config.get("compiler", None)
    if not compiler:
        log_error("Compiler was not set")
        sys.exit(1)

    # read compiler options (optional)
    options = config.get("options", None)
    if options:
        compiler_args.append(options)

    program_file = config.get("program", None)
    if program_file:
        output_file = program_file.replace(".p4", "") + '.json'
        if compiler == 'p4c':
            # The p4c compiler accepts only a directory for output files
            # Instead of a file name since it creates not only the .json,
            # but also auxiliary files
            output = os.path.dirname(os.path.realpath(output_file))
        elif compiler.startswith('p4c-'):
            output = output_file
        else:
            log_error('Unknown Compiler %s' % compiler)
            sys.exit()

        compiler_args.append('"%s"' % program_file)
        compiler_args.append('-o "%s"' % output)
    else:
        log_error("Unknown P4 file %s" % program_file)
        sys.exit(1)

    print(compiler + ' %s' % ' '.join(compiler_args))
    return_value = run_command(compiler + ' %s' % ' '.join(compiler_args))

    if return_value != 0:
        raise CompilationError

    return output_file

def compile_all_p4(config):
    """Compiles all the .p4 files that are found in the project configuration file.
    Avoid compiling the same P4 program twice.

    Args:
        config: dictionary of topology configuration (from configuration file)

    Returns:
        dictionary of JSON file names, keyed by switch names
    """
    switch_to_json = {}
    p4programs_already_compiled = {}
    topo = config.get("topology", None)

    #mandatory defaults if not defined we should complain
    default_p4 = config.get("program", None)
    default_options = config.get("options", None)

    #non mandatory defaults.
    default_compiler = config.get("compiler", DEFAULT_COMPILER)

    default_config = {"program": default_p4, "options": default_options, "compiler": default_compiler}

    if default_p4 and default_options:
        json_name = compile_p4_to_bmv2(default_config)
        p4programs_already_compiled[default_p4] = json_name
    else:
        log.debug('Default program was not compiled')

    if topo:
        switches = topo.get("switches", None)
        if switches:
            # make a set with all the P4 programs to compile
            for switch_name, sw_attributes in switches.iteritems():
                #merge defaults with switch attributes
                switch_conf = default_config.copy()
                switch_conf.update(sw_attributes)

                program_name = switch_conf.get("program", None)

                if program_name:
                    json_name = p4programs_already_compiled.get(program_name, None)
                    if json_name:
                        sw_attributes.update({"json":json_name})
                        switch_to_json[switch_name] = sw_attributes
                    else:
                        json_name = compile_p4_to_bmv2(switch_conf)
                        sw_attributes.update({"json": json_name})
                        switch_to_json[switch_name] = sw_attributes
                        p4programs_already_compiled[program_name] = json_name
                else:
                    raise Exception('Did not find a P4 program for switch %s' % switch_name)
        return switch_to_json

    raise Exception('No topology or switches in configuration file.')

def open_cli_process(thrift_port, cli=DEFAULT_CLI):

    return subprocess.Popen([cli, '--thrift-port', str(thrift_port)],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def add_entries(thrift_port, entries, log_output = None, cli=DEFAULT_CLI):
    """Add entries to P4 switch using the DEFAULT_CLI.

    Args:
        thrift_port: Thrift port number used to communicate with the P4 switch
        entries: list of entries to add to the switch
        log_output: file where to log cli outputs
        cli: CLI executable
    """
    if isinstance(entries, list):
        entries = '\n'.join(entries)

    p = open_cli_process(thrift_port, cli)
    stdout, stderr = p.communicate(input=entries)

    if log_output:
        with open(log_output, "a") as log_file:
            log_file.write(stdout)

    return stdout

def read_register(register, idx, thrift_port=9090):
    """Read register value from P4 switch using the DEFAULT_CLI.

    Args:
        register: register name
        idx: index of value in register
        thrift_port: Thrift port number used to communicate with the P4 switch

    Returns:
        Register value at index
    """
    p = open_cli_process(thrift_port, DEFAULT_CLI)
    stdout, stderr = p.communicate(input="register_read %s %d" % (register, idx))
    reg_val = filter(lambda l: ' %s[%d]' % (register, idx) in l, stdout.split('\n'))[0].split('= ', 1)[1]
    return long(reg_val)

def read_tables(thrift_port=9090, cli=DEFAULT_CLI):
    """List tables available on the P4 switch using the simple_switch_CLI.

    Args:
        thrift_port: Thrift port number used to communicate with the P4 switch
        cli: CLI executable
    """
    p = open_cli_process(thrift_port, cli)

    stdout, stderr = p.communicate(input="show_tables")
    return stdout
