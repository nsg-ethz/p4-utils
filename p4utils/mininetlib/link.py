from mininet.link import Link, TCIntf


# Since the interface type can be set globally with Mininet by passing it to the network
# constructor, this class is not used since its only relevant purpose is to use TCIntf
# interface.

class TCLink(Link):
    "Link with symmetric TC interfaces configured via opts"
    def __init__( self, node1, node2, port1=None, port2=None,
                  intfName1=None, intfName2=None,
                  addr1=None, addr2=None, **params ):

        _params1 = params.pop("params1", None)
        _params2 = params.pop("params2", None)

        params1 = params.copy()
        if _params1:
            params1.update(_params1)
        params2 = params.copy()
        if _params2:
            params2.update(_params2)

        super().__init__(node1, node2, port1=port1, port2=port2,
                         intfName1=intfName1, intfName2=intfName2,
                         cls1=TCIntf,
                         cls2=TCIntf,
                         addr1=addr1, addr2=addr2,
                         params1=params1,
                         params2=params2)