from mininet.net import Mininet

class P4Mininet(Mininet):

    def __init__(self, *args, **kwargs):
        """
        Adds p4switches
        :param args:
        :param kwargs:
        """
        self.p4switches = []
        super(P4Mininet, self).__init__(*args, **kwargs)

    def build(self):
        """
        Build mininet
        :return:
        """

        super(P4Mininet, self).build()

        for switch in self.switches:
            name = switch.name
            if self.topo.isP4Switch(name):
                self.p4switches.append(switch)
