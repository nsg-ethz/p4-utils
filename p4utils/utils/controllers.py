import os
import subprocess
import sys
import bmv2
import helper

class ThriftController:
    """
    This controller reads commands from a thrift configuration
    file and uses it to set up the thrift switch

    Attributes:
        sw_name (string): name of the switch to configure
        thrift_port (int): thrift server port number
        quiet (bool): whether to show messages on execution
    """
    def __init__(self, sw_name, thrift_port, quiet=False):
        self.sw_name = sw_name,
        self.thrift_port = thrift_port
        self.quiet = quiet

    def logger(self, *items):
        if not self.quiet:
            print(' '.join(items))

    def conf(self, conf_path, log_dir='/tmp', log_enabled=True):
        """
        This method configures the switch with the provided file.

        Arguments:
            conf_path (string): path of the configuration file
            log_path (string): path of the log file
            log_enabled (bool): whether to save logs or not
        """
        cli = 'simple_switch_CLI'
        log_path = log_dir + '/{}_cli_output.log'.format(self.sw_name)
        if not os.path.isfile(conf_path):
            self.logger('Could not find file {} for switch {}'.format(conf_path, self.sw_name))
        else:
            self.logger('Configuring switch {} with thrift file {}'.format(self.sw_name, conf_path))
            with open(conf_path, "r") as fin:
                entries = [x.strip() for x in fin.readlines() if x.strip() != ""]
                entries = [x for x in entries if ( not x.startswith("//") and not x.startswith("#")) ]
                if log_enabled:
                    with open(log_path, 'w') as fout:
                        subprocess.Popen([cli, '--thrift-port', str(self.thrift_port)],
                                    stdin=fin, stdout=fout)
                else:
                    subprocess.Popen([cli, '--thrift-port', str(self.thrift_port)],
                                stdin=fin, stdout=None)


class RuntimeController:
    pass
