from mininet.cli import CLI
from mininet.log import info, output, error

class P4CLI(CLI):

    def __init__(self,*args,**kwargs):

        CLI.__init__(self,*args,**kwargs)


    def do_p4(self,line=""):
        """Start/stop/restart the mininet generator
           Usage: mininet start/stop/restart node
        """
        args = line.strip().split()
        if len(args) == 2:
            cmd = args[0]
            host = args[1]

            if cmd == "start":
                if host == "all":
                    self.minigenerator.start()
                elif host in self.minigenerator.mininet:
                    self.minigenerator.start_node(host)
                else:
                    error('invalid host')
            elif cmd == "stop":
                if host == "all":
                    self.minigenerator.stop()
                elif host in self.minigenerator.mininet:
                    self.minigenerator.stop_node(host)
                else:
                    error('invalid host')
            elif cmd == "restart":
                if host == "all":
                    self.minigenerator.restart()
                elif host in self.minigenerator.mininet:
                    self.minigenerator.restart_node(host)
                else:
                    error('invalid host')
            else:
                error('invalid command: start stop restart')

        else:
            error('invalid number of args: minigenerator cmd node')


    # def do_stoprouter(self,line=""):
    #
    #     """stop zebra and ospf from a router"""
    #     router_name = line.split()
    #     if not router_name or len(router_name) > 1:
    #         error('usage: stoprouter router\n')
    #     else:
    #         router_name = router_name[0]
    #         if router_name not in self.mn:
    #             error("router %s not in the network\n" % router_name)
    #         else:
    #             router = self.mn[router_name]
    #             router.router.delete()
    #
    # def do_startrouter(self,line=""):
    #
    #     """start zebra and ospf from a router"""
    #     router_name = line.split()
    #     if not router_name or len(router_name) > 1:
    #         error('usage: startrouter router\n')
    #     else:
    #         router_name = router_name[0]
    #         if router_name not in self.mn:
    #             error("router %s not in the network\n" % router_name)
    #         else:
    #             router = self.mn[router_name]
    #             router.router.start()
    #
    # def do_rebootquaggas(self, line=""):
    #     """restarts zebra and ospfd from all routers"""
    #
    #     for r in self.mn.routers:
    #         r.router.delete()
    #         r.router.start()
    #
    # def do_rebootquagga(self,line=""):
    #
    #     """restarts zebra and ospf from a router"""
    #     router_name = line.split()
    #     if not router_name or len(router_name) > 1:
    #         error('usage: rebootquagga router\n')
    #     else:
    #         router_name = router_name[0]
    #         if router_name not in self.mn:
    #             error("router %s not in the network\n" % router_name)
    #         else:
    #             router = self.mn[router_name]
    #             router.router.delete()
    #             router.router.start()
