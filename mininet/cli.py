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
                p4switch.p4switch.delete()

    def do_p4switch_start(self,line=""):

        """start again simple switch from namespace"""
        switch_name = line.split()
        if not switch_name or len(switch_name) > 1:
            error('usage: p4switch_start <p4switch name>\n')
        else:
            switch_name = switch_name[0]
            if switch_name not in self.mn:
                error("p4switch %s not in the network\n" % switch_name)
            else:
                p4switch = self.mn[switch_name]
                p4switch.p4switch.start()

    def do_p4switches_reboot(self, line=""):
        """reboot all p4 switches with new program """

        for r in self.mn.p4switchs:
            r.p4switch.delete()
            r.p4switch.start()

    def do_p4switch_reboot(self,line=""):

        """reboot a p4 switch with new program"""
        switch_name = line.split()
        if not switch_name or len(switch_name) > 1:
            error('usage: p4switch_reboot <p4switch name>\n')
        else:
            switch_name = switch_name[0]
            if switch_name not in self.mn:
                error("p4switch %s not in the network\n" % switch_name)
            else:
                p4switch = self.mn[switch_name]
                p4switch.p4switch.delete()
                p4switch.p4switch.start()
