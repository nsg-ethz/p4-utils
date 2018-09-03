from p4utils.utils.utils import read_entries, add_entries
import os

class AppController(object):

    def __init__(self, conf, net, log_dir, log_enabled, quiet=False):
        self.conf = conf
        self.net = net
        self.log_dir = log_dir
        self.log_enabled = log_enabled
        self.quiet = quiet

    def logger(self, *items):
        if not self.quiet:
            print ' '.join(items)

    def start(self):

        cli = self.conf['switch_cli']
        for sw_name, sw_dict in self.conf.get('topology',{}).get('switches', {}).items():
            if 'cli_input' not in sw_dict:
                continue
            # get the port for this particular switch's thrift server
            sw_obj = self.net.get(sw_name)
            thrift_port = sw_obj.thrift_port

            cli_outfile = '%s/%s_cli_output.log' % (self.log_dir, sw_name) if self.log_enabled else None

            cli_input_commands = sw_dict['cli_input']
            self.logger('Configuring switch %s with file %s' % (sw_name, cli_input_commands))

            if os.path.exists(cli_input_commands):
                entries = read_entries(cli_input_commands)
                add_entries(thrift_port, entries, cli_outfile, cli)
            else:
                self.logger('Could not find file %s for switch %s' % (cli_input_commands, sw_name))


    def stop(self):
        pass
