from __future__ import print_function
import sys, os
import subprocess
import json
from mininet import log

import psutil

def check_listening_on_port(port):
    for c in psutil.net_connections(kind='inet'):
        if c.status == 'LISTEN' and c.laddr[1] == port:
            return True
    return False

class CompilationError(Exception):
    pass

def last_modified(input_file, output_file):
    """

    :param input_file:
    :param output_file:
    :return: true if input_file is newer than output_file or if output file does not exist.
    """

    if (not os.path.exists(input_file)):
        log.error("input file does not exist")

    if (not os.path.exists(output_file)):
        return True

    return os.path.getmtime(input_file) >  os.path.getmtime(output_file)

def get_imported_files(input_file):

    includes = []

    with open(input_file, "r") as f:
        lines = f.readlines()

    for line in lines:
        tmp = line.strip()
        if tmp.startswith("#include"):
            file_name = tmp.split(" ")[1]

            #find if it is surrounded by <>
            if  not (file_name.startswith("<") and file_name.endswith(">")):
                includes.append(file_name.strip('"'))

    return includes

#TODO: can be improved. Main problem is that it assumes project structure. it should be able to locate those files without assumtions
def check_imports_last_modified(input_file, import_last_modifications):

    compile_flag = False
    for import_file in get_imported_files(input_file):

        #processing assuming that we are in root directory
        if import_file.startswith("../"):
            import_file = import_file[3:]

        elif import_file.startswith("include/"):
            import_file = "p4src/" + import_file

        if (not os.path.exists(import_file)):
            log.error("File %s does not exist \n" % import_file)
            #maybe i should rise an error
            return False

        #add if they are bigger or not.
        print(import_file)
        last_time = os.path.getmtime(import_file)
        if last_time > import_last_modifications.get(import_file, 0):
            import_last_modifications[import_file] = last_time
            compile_flag = True

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
    with open(filename,"r") as f:
        entries = [x.strip() for x in f.readlines() if x.strip() != ""]
    return entries

def compile_p4_to_bmv2(config):

    compiler_args = []

    language = config.get("language", None)
    if language == 'p4-14':
        compiler_args.append('--p4v 14')
    elif language == 'p4-16':
        compiler_args.append('--p4v 16')
    else:
        log_error('Unknown language:', language)
        sys.exit(1)

    # Compile the program.
    program_file = config.get("program", None)
    if program_file:
        output_file = program_file.replace(".p4","") + '.json'
        compiler_args.append('"%s"' % program_file)
        compiler_args.append('-o "%s"' % output_file)
    else:
        log_error("Unknown P4 file %s" % program_file)

    print(compiler_args)
    rv = run_command('p4c-bm2-ss %s' % ' '.join(compiler_args))

    if rv != 0:
        raise CompilationError

    return output_file

def compile_all_p4(configuration):

    """ Compiles all the .p4 files that are found in the project
    configuration file. Avoid compiling same .p4 program twice.
    """

    default_p4 = configuration.get("program", None)
    switch_to_json = {}
    p4programs_already_compiled = {}
    topo = configuration.get("topology", None)

    if default_p4:
        json_name = compile_p4_to_bmv2({"language": configuration.get("language", ""), "program": default_p4})
        p4programs_already_compiled[default_p4] = json_name

    if topo:
        switches = topo.get("switches", None)
        if switches:
            #make a set with all the p4 programs to compile
            for switch_name, values in switches.iteritems():
                program_name = values.get("program", None)
                if program_name:
                    json_name = p4programs_already_compiled.get(program_name, None)
                    if json_name:
                        switch_to_json[switch_name] = json_name
                    else:
                        json_name = compile_p4_to_bmv2({"language": configuration.get("language", ""), "program": program_name})
                        switch_to_json[switch_name] = json_name
                        p4programs_already_compiled[program_name] = json_name
                elif default_p4:
                    switch_to_json[switch_name] = p4programs_already_compiled[default_p4]
                else:
                    raise Exception('Did not find a p4 program for switch %s' % switch_name)
        return switch_to_json

    raise Exception('No topology or switches in configuration')

def add_entries(thrift_port=9090, entries=None):
    assert entries

    if type(entries) == list:
        entries = '\n'.join(entries)

    print(entries)

    p = subprocess.Popen(['simple_switch_CLI', '--thrift-port', str(thrift_port)], stdin=subprocess.PIPE)
    p.communicate(input=entries)

def read_register(register, idx, thrift_port=9090):
    p = subprocess.Popen(['simple_switch_CLI', '--thrift-port', str(thrift_port)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate(input="register_read %s %d" % (register, idx))
    reg_val = filter(lambda l: ' %s[%d]' % (register, idx) in l, stdout.split('\n'))[0].split('= ', 1)[1]
    return long(reg_val)
