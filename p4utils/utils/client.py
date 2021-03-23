import os
import subprocess
from mininet.log import debug, info, warning

from p4utils.utils.helper import *

class ThriftClient:
    """
    This controller reads commands from a thrift configuration
    file and uses it to set up the thrift switch.

    Attributes:
        cli_bin (string)    : client binary file path.
        conf_path (string)  : path of the configuration text file.
        log_enabled (bool)  : whether to enable logs.
        log_dir (string)    : directory to store logs.
        thrift_port (int)   : thrift server thrift_port number.
        sw_name (string)    : name of the switch to configure.
    """
    cli_bin = 'simple_switch_CLI'

    @classmethod
    def set_binary(self, cli_bin):
        """Set class default binary"""
        ThriftController.cli_bin = cli_bin

    def __init__(self, thrift_port,
                 sw_name,
                 cli_bin=None,
                 conf_path=None,
                 log_enabled=True,
                 log_dir='/tmp',
                 **kwargs):
        
        self.set_conf(conf_path)
        self.log_enabled = log_enabled
        self.log_dir = log_dir
        self.sw_name = sw_name
        self.thrift_port = thrift_port

        if cli_bin is not None:
            self.set_binary(cli_bin)

    def get_conf(self):
        """Returns self.conf_path"""
        return self.conf_path

    def set_conf(self, conf_path):
        """Set the configuration file path."""
        # Check whether the conf file is valid
        if conf_path is not None:
            self.conf_path = os.path.realpath(conf_path)
        else:
            self.conf_path = None

    def configure(self):
        """
        This method configures the switch with the provided file.
        """
        if self.conf_path is not None:
            if not os.path.isfile(self.conf_path):
                raise FileNotFoundError('Could not find file {} for switch {}'.format(self.conf_path, self.sw_name))
            elif check_listening_on_port(self.thrift_port):
                log_path = self.log_dir + '/{}_cli_output.log'.format(self.sw_name)
                with open(self.conf_path, 'r') as fin:
                    entries = [x.strip() for x in fin.readlines() if x.strip() != '']
                    entries = [x for x in entries if ( not x.startswith('//') and not x.startswith('#')) ]
                    entries = '\n'.join(entries)
                    p = subprocess.Popen([self.cli_bin, '--thrift-port', str(self.thrift_port)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = p.communicate(input=entries.encode())
                    if self.log_enabled:
                        with open(log_path, 'w') as log_file:
                            log_file.write(stdout.decode())
                info('Configured switch {} with thrift file {}\n'.format(self.sw_name, self.conf_path))
            else:
                raise ConnectionRefusedError('Could not connect to switch {} on port {}'.format(self.sw_name, self.thrift_port))
        else:
            raise FileNotFoundError('Could not find file {} for switch {}'.format(self.conf_path, self.sw_name))


class RuntimeController:
    pass
