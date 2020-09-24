Assignment Strategies and helpers
=================================

P4-utils provides some default addressing assignment strategies that will set for you 
the mac and ip addresses of the network interfaces. Depending on the situation one 
strategy might be more useful than another. For example, if we want to implement a 
pure layer 3 functionality we might want to assign IPs from different subnetworks to each
switch interface. If we want to implement a full layer 2 functionality we might want to 
give all nodes in the network an ip from the same subnet.

As explained in the main documentation when you use the default `topo_module`
you can use different assignment strategies. Assignment strategies are needed due to
the fact that p4-switches can work at any network layer (L2, L3, ...), and thus 
there is no way to automatically configure the hosts, and switches without knowing what will switches do.

You can chose which strategy to use in the `p4app.json` file as follows (for layer 2):

```javascript
"topology": {
    "assignment_strategy": "l2",
    "links": [
        ["h1", "s1"],
        ["h2", "s1"]
    ],
    "hosts": {
        "h1": {},
        "h2": {}
    },
    "switches": {
        "s1": {}
    }
}
```

P4 utils implements the following strategies:

### Layer 2 (l2)

All switches in the network are assumed to work at layer 2, thus
all hosts get assigned to the same subnetwork. Therefore hosts get automatically assigned
with IPs belonging to the same subnet (starting from `10.0.0.1/16`). 
Since by default `p4-switches` do not broadcast packets, `p4-utils` will automatically 
populate each host's ARP table with the MAC addresses of all the other hosts. This option can be 
disabled setting `auto_arp_tables` to false. 

For example, after starting the topology, `h1` arp table is already loaded with h2's MAC address:

<img src="images/arp_example.png" title="arp example">

To disable automatic ARP population we added the following line to the topology section of the p4app.json:

```
"auto_arp_tables": false
```


### Mixed

This is not a real l2 or l3 assignment strategy, but since p4 switches can work at
any layer, it can be useful for easy prototyping. Hosts connected to the same switch
will be assigned an ip within the same subnet. Hosts connected to another switch will belong
to another subnet. Each hosts can only be connected to a single switch, which at the same time
is assigned to be the L3 gatway. Hosts connected to a different switch will belong to a
different `/24` subnet. If you use the namings `hX` and `sX` (e.g h1, h2, s1...), the IP
assignment goes as follows: `10.x.x.y`. Where `x` is the switch id (upper and lower bytes),
and `y` is the host id. For example, in the topology above, `h1` gets `10.0.1.1` and `h2` gets `10.0.6.2`.

### Layer 3 (l3)

Unlike the `mixed` strategy where hosts connected to the same
switch formed a subnetwork and each switch formed a different domain. In the `l3` assignment, we consider switches to only work
at the layer 3, meaning that each interface must belong to a different subnetwork. If you use the namings `hY` and `sX` (e.g h1, h2, s1, s2...),
the IP assignment will go as follows:

   1. Host IPs: `10.x.y.2`, where `x` is the id of the gateway switch, and `y` is the host id.
   2. Switch ports directly connected to a host: `10.x.y.1`, where `x` is the id of the gateway switch, and `y` is the host id.
   3. Switch to Switch interfaces: `20.sw1.sw2.<1,2>`. Where `sw1` is the id of the first switch (following the order in the `p4app` link definition), `sw2` is the
   id of the second switch. The last byte is 1 for sw1's interface and 2 for sw2's interface.

Note that it is the first time we assign IP addresses to a switch. However, it is very important to note that actually `p4-utils` will not assign those IPs
to the switches, but it will save them so they can be `virtually` used for some switch functionality, like for example when the switch needs to reply to 
packets with its own ip (i.e `traceroute`).

## Manual

Can be used when your topology will be formed by heterogeneous devices, you have to manually 
set the IP to each interface and host gateways. See the main documentation for more information.


## How to easily get addressing information

Sometimes you need to know which IPs, mac addresses or how things are connected 
in order to populate switch tables or decide how the control plane has to do 
certain things. If your `p4` program is not compilable you wont be able to start
the topology since `p4run` will fail to load the `p4` switches. For that, we provide 
you the option to run your `p4app.json` topology on empty p4 switches that do not do anything. 
That, will give you the chance to check which IPs and MAC addresses were assigned to hosts and
links. To run empty programs use the `--empty-p4` command flag.

```
sudo p4run --empty-p4
```

We furthermore provide a `CLI` command to easily display the most important 
features of the current network. With the command `printNetInfo` you can get 
a perfect summary of your switches and hosts. For both hosts and switches you 
will get very  useful information such as: the thrift-port, cpu-port, 
port indexes and to where  they connect, addresses and link attributes. 

As an example you can see the info of a layer 3 assignment strategy topology:

<img src="images/net_info_example.png" title="net info example">

