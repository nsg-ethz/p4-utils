from mininet.net import Mininet

class P4Mininet(Mininet):
    """P4Mininet is the Mininet Class extended with P4 switches."""

    def __init__(self, *args, **kwargs):
        """Adds p4switches."""
        self.p4switches = []
        super(P4Mininet, self).__init__(*args, **kwargs)

    def build(self):
        """Build P4Mininet."""
        super(P4Mininet, self).build()

        for switch in self.switches:
            name = switch.name
            if self.topo.isP4Switch(name):
                self.p4switches.append(switch)
