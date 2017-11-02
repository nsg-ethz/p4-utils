from __future__ import print_function
import sys, os
import subprocess
from mininet import log

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

def check_imports_last_modified(input_file, import_last_modifications):

    compile_flag = False
    for import_file in get_imported_files(input_file):

        if (not os.path.exists(import_file)):
            log.error("File %s does not exist \n" % import_file)
            #maybe i should rise an error
            return False

        #add if they are bigger or not.
        last_time = os.path.getmtime(import_file)
        if last_time > import_last_modifications.get(import_file, 0):
            import_last_modifications[import_file] = last_time
            compile_flag = True

    return compile_flag



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
    program_file = config.get("program_file", None)
    if program_file:
        output_file = program_file.replace(".p4","") + '.json'
        compiler_args.append('"%s"' % program_file)
        compiler_args.append('-o "%s"' % output_file)
    else:
        log_error("Unknown P4 file %s" % program_file)

    rv = run_command('p4c-bm2-ss %s' % ' '.join(compiler_args))

    if rv != 0:
        log_error('Compile failed.')
        sys.exit(1)

    return output_file

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
