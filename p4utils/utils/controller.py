import os
import subprocess
from mininet.log import debug, info, warning

class ThriftController:
    """
    This controller reads commands from a thrift configuration
    file and uses it to set up the thrift switch.

    Attributes:
        sw_name (string)    : name of the switch to configure.
        thrift_port (int)   : thrift server port number.
        cli_bin (strin)     : path to the controller client binary
    """
    cli_bin = 'simple_switch_CLI'

    @classmethod
    def set_binary(self, cli_bin):
        """Set class default binary"""
        ThriftController.cli_bin = cli_bin

    def __init__(self, sw_name, thrift_port, cli_bin=None):
        self.sw_name = sw_name
        self.thrift_port = thrift_port

        if cli_bin is not None:
            self.set_binary(cli_bin)

    def conf(self, conf_path, log_dir='/tmp', log_enabled=True):
        """
        This method configures the switch with the provided file.

        Arguments:
            conf_path (string)  : path of the configuration file.
            log_path (string)   : path of the log file.
            log_enabled (bool)  : whether to save logs or not.
        """
        cli = 'simple_switch_CLI'
        log_path = log_dir + '/{}_cli_output.log'.format(self.sw_name)
        if not os.path.isfile(conf_path):
            raise FileNotFoundError('Could not find file {} for switch {}'.format(conf_path, self.sw_name))
        else:
            with open(conf_path, "r") as fin:
                entries = [x.strip() for x in fin.readlines() if x.strip() != ""]
                entries = [x for x in entries if ( not x.startswith("//") and not x.startswith("#")) ]
                entries = '\n'.join(entries)
                p = subprocess.Popen([cli, '--thrift-port', str(self.thrift_port)],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = p.communicate(input=entries.encode())
                if log_enabled:
                    with open(log_path, "w") as log_file:
                        log_file.write(stdout.decode())
            info('Configured switch {} with thrift file {}\n'.format(self.sw_name, conf_path))


class RuntimeController:
    pass
