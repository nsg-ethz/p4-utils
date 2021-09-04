Usage
=====

__ advanced_usage.html

In the following sections, we present a simple overview of the basic features of P4-Utils.
In case you are looking for more advanced options, please have a look at the `advanced usage
section`__.

To make the explaination simpler and more concrete, we consider the following network
example. We will go through the configuration files that allow the user to define and
use such a topology.

.. image:: _images/l2_topology.png
   :align: center

As we can see in the figure above, we have four hosts connected to a switch. All the
switches are placed in the same subnetwork ``10.0.0.0/16``. We have to create the
network and establish connectivity among the hosts via L2 forwarding

Network Setup
-------------

To create a network we can use two different methods:

- __ #python

  the `Python method`__ relies on writing a network defining script 
  that makes use of :py:class:`~p4utils.mininetlib.network_API.NetworkAPI`,

- __ #json

  the `JSON method`__, on the other hand, relies on writing a JSON network
  definition file using the specifications of the parser 
  :py:class:`~p4utils.p4run.AppRunner`.

Python
++++++

The Python method is a newly introduced feature that allows to programmatically
specify which elements are present in the network and how they are connected.
It is based on the :py:class:`~p4utils.mininetlib.network_API.NetworkAPI`, an API that
has a lot of methods to precisely define the network structure.

Let us create a file called ``network.py``. In order to define the network, we first 
need to import the required module and create a ``NetworkAPI`` object::

  from p4utils.mininetlib.network_API import NetworkAPI

  net = NetworkAPI()

We can also set the level of details for the log shown during the execution of
the script::

  net.setLogLevel('info')

Other important options are those involving ARP tables of hosts. One can choose
to disable static ARP entries for hosts within the same subnetwork and their
gateways by using the methods 
:py:meth:`~p4utils.mininetlib.network_API.NetworkAPI.disableArpTables()` and 
:py:meth:`~p4utils.mininetlib.network_API.NetworkAPI.disableGwArp()`. These
options do not apply to our simple example.

.. Important::
   By default, the ARP tables of the hosts of the network are populated in a static 
   way at network starting time. In this way, ARP requests have not to be taken into
   account when operating the network.

Possible **logLevel** values are the follwing (in decreasing order of detail):

- ``debug``
- ``info``
- ``output``
- ``warning``
- ``error``
- ``critical``

Now we are ready to define our topology. We start by adding the nodes::

  net.addP4Switch('s1')
  net.addHost('h1')
  net.addHost('h2')
  net.addHost('h3')
  net.addHost('h4')

As one may notice, we added P4 switch called ``s1`` and four hosts named ``h1``,
``h2``, ``h3``, ``h4``.

.. Warning::
   When adding nodes, make sure that they all have **unique** names.

For what concerns the P4 switch, we need to configure it with a P4 program. Let us
assume that we have a P4 program called ``l2_forwarding.p4`` in the same folder of
the Python script. We use the following line to add it to ``s1``::

  net.setP4Source('s1','l2_forwarding.p4')

This file will be compiled and then passed to the switch.

Now we are ready to set up the links::

  net.addLink('s1', 'h1')
  net.addLink('s1', 'h2')
  net.addLink('s1', 'h3')
  net.addLink('s1', 'h4')

.. Warning::
   Links must be added after the nodes because, when the method 
   :py:meth:`~p4utils.mininetlib.network_API.NetworkAPI.addLink()` is called,
   the program checks if the connected nodes actually exist in the network.

It may be useful to specify also the port numbers of the nodes that are connected through
a link. This makes the switch configuration easier because port numbers are given.

::

  net.setIntfPort('s1', 'h1', 1)  # Set the number of the port on s1 facing h1
  net.setIntfPort('h1', 's1', 0)  # Set the number of the port on h1 facing s1
  net.setIntfPort('s1', 'h2', 2)  # Set the number of the port on s1 facing h2
  net.setIntfPort('h2', 's1', 0)  # Set the number of the port on h2 facing s1
  net.setIntfPort('s1', 'h3', 3)  # Set the number of the port on s1 facing h3
  net.setIntfPort('h3', 's1', 0)  # Set the number of the port on h3 facing s1
  net.setIntfPort('s1', 'h4', 4)  # Set the number of the port on s1 facing h4
  net.setIntfPort('h4', 's1', 0)  # Set the number of the port on h4 facing s1

.. Important::
   In case you do not specify port numbers, an automatic assignment will be performed. The
   automatic assignment is **consistent** among different executions of the network script.

If we want to limit the bandwidth of the link between ``s1`` and ``h1`` to 5 Mbps, we can
use the following method::

  net.setBw('s1','h1', 5)

If we want to set 5 Mbps as the maximum bandwidth for all the links at once, we can use::

  net.setBwAll(5)

Now that we have defined the topology, we need to assign IPs and MACs to the nodes. We have
three ways of doing this:

- If nothing is specified, all the nodes are placed in the network ``10.0.0.0/8`` and 
  the MACs are random.

- One can also manually specify MACs and IPs for every interface in the network by using 
  the following methods:

  + :py:meth:`~p4utils.mininetlib.network_API.NetworkAPI.setIntfIp()` sets the IP address
    of the interface::

      net.setIntfIp('h1','s1','10.0.0.1/24') # The interface of h1 facing s1 has IP 10.0.0.1/24

  + :py:meth:`~p4utils.mininetlib.network_API.NetworkAPI.setIntfMac()` sets the MAC address
    of the interface::
    
      net.setIntfIp('h1','s1','00:00:00:00:00:01') # The interface of h1 facing s1 has MAC 00:00:00:00:00:01

- __ #automated-assignment-strategies

  We can use predefined `automated assignment strategies`__. 
   
  + **l2** strategy can be selected by specifying::

      net.l2()

  + **mixed** strategy can be selected by specifying::

      net.mixed()

  + **l3** strategy can be selected by specifying::

      net.l3()

  In our case, since the hosts are in the same network, we can use the **l2** strategy.

Now, we can set up nodes generic options. For example, we can enable ``.pcap`` files
dumping on disk and logging for all the P4 switches::

  net.enablePcapDumpAll()
  net.enableLogAll()

.. Note::
   One can also specify only some switches using the methods 
   :py:meth:`~p4utils.mininetlib.network_API.NetworkAPI.enablePcapDump()` and 
   :py:meth:`~p4utils.mininetlib.network_API.NetworkAPI.enableLog()`.

Finally, we can enable the network client and start the network::

  net.enableCli()
  net.startNetwork()

To execute the network, we can simply run our Python script with super user rights::

  sudo python3 network.py

.. Important::
   This guide is just a basic overview of all the methods available. Please check
   out the documentation of :py:class:`p4utils.mininetlib.network_API.NetworkAPI` to 
   discover more advanced techniques involving also routers.

JSON
++++

The JSON method is the legacy method for defining a network topology. It is based 
on the :py:class:`~p4utils.p4run.AppRunner`, a parser that reads the JSON files 
and creates a network accordingly. Let us take a look at the JSON file that defines
the example network::

  {
    "p4_src": "l2_forwarding.p4",
    "cli": true,
    "pcap_dump": true,
    "enable_log": true,
    "topology": {
      "assignment_strategy": "l2",
      "default": {
        "bw": 10
      }, 
      "links": [["h1", "s1"], ["h2", "s1"], ["h3", "s1"], ["h4", "s1"]],
      "hosts": {
        "h1": {
        },
        "h2": {
        }
        ,
        "h3": {
        }
        ,
        "h4": {
        }
      },
      "switches": {
        "s1": {
        }
      }
    }
  }

The JSON structure is very simple and intuitive. We have that:

- The field ``p4_src`` indicates the default P4 program that has to be passed
  to the switches. In the example, we assume that we have a P4 file called 
  ``l2_forwarding.p4`` in the same folder of the JSON file.
- The field ``cli`` specifies whether we want to activate the network client after
  the network starts.
- The field ``pcap_dump`` indicates whether we want to activate the packet sniffing
  on the interfaces of the switches or not. The sniffed packets are then saved 
  in ``.pcap`` files.
- The field ``enable_log`` enables or disables the log for switches.
- The ``topology`` field gathers some topology specific instructions:

  + __ #automated-assignment-strategies

    ``assignment_strategy`` allows the user to specify an `automated strategy`__ for 
    assigning addresses to the interfaces. Possible values are ``l2``, ``mixed`` and ``l3``.

  + ``default`` is a collection of default settings that apply to every link.
    For instance, in the JSON example, we force the bandwidth of every link to be 5 Mbps.
    Basically, every parameter that is used to configure links can be specified here to
    set it as default. In addition, two more options can be put here to disable ARP 
    static entries in hosts (which are enabled by default)::

      "auto_arp_tables": false,
      "auto_gw_arp": false

  + ``links`` is simply a list of all the links that are present in the topology. You
    can also specify custom options for a link. Basically, every parameter that can be 
    passed to the constructor of :py:class:`mininet.link.Link`, can be used as option here
    by putting it in a dictionary after the name of the connected nodes. For example, the
    following will set the addresses of the link and limit its bandwidth to 5 Mbps::

      ["h1", "s1", {"bw": 5, "addr1": "00:00:00:00:00:01", "addr2": "00:01:00:00:00:01", "params1": {"ip":"10.0.0.1/24"}}]

    Every parameter whose name contains ``1`` refers to the interface on ``h1``. On the 
    other hand, every parameter whose name contains ``2`` refers to the interface on ``h2``.
    Parameters without numbers in their names simply apply to the whole link.

  + ``hosts`` is a dictionary of hosts. Each host has its own dictionary to pass options.
    If no custom options are passed, then the host dictionary must be left empty.
    For example, the following will set ``10.0.0.254`` as the default gateway for ``h1``::

      "h1": {"defaultRoute": "via 10.0.0.254"}

  + ``switches`` is a dictionary of switches. Each switch has its own dictionary to pass options.
    If no custom options are passed, then the switch dictionary must be left empty.
    For example, the following will set a custom P4 program for switch ``s1``::

      "s1": {"p4_src": "custom.p4"}

To run the network, we simply execute the following command with super user rights::

  sudo p4run --config <path to the JSON configuration file>

In case the JSON configuration file is called ``p4app.json``, we can run the network with::

  sudo p4run

.. Important::
   This explaination is only a brief overview of the most common options available with
   the JSON network configuration file. Please check out the documentation of the module 
   :py:mod:`p4utils.p4run` to discover more advanced techniques involving also routers.

Automated Assignment Strategies
-------------------------------

Specifying the addresses of every interface in the network can be long and cumbersome.
For this reason one can use automated assignment strategies that performs this work for
you, following simple rules.

.. Warning::
   All of the following strategies assume that:

   - Each host is connected to exactly one switch.
   - Only switches and hosts are allowed.
   - Parallel links are not allowed.

l2
++

**l2** strategy places all the devices inside the same IPv4 network (``10.0.0.0/16``). It
is implemented by :py:meth:`~p4utils.mininetlib.network_API.NetworkAPI.l2()`. The IPs and the
MACs are assigned according to the numbers present in the host names. Please check out the 
implementation for further details.

mixed
+++++

**mixed** strategy places the hosts connected to the same switch in the same subnetwork
and different switches (even those linked together) in different ones. It is implemented
by :py:meth:`~p4utils.mininetlib.network_API.NetworkAPI.mixed()`. The IPs and the
MACs are assigned according to the numbers present in the host and switch names. Please
check out the implementation for further details.

l3
++

**l3** strategy places all the hosts in a different subnetwork that is shared
with the fake IP address of the switch port they are connected to. It is implemented
by :py:meth:`~p4utils.mininetlib.network_API.NetworkAPI.l3()`. The IPs and the
MACs are assigned according to the numbers present in the host and switch names.
Please check out the implementation for further details.

Network Client
--------------

The network client is implemented by :py:class:`p4utils.mininetlib.cli.P4CLI`. You can 
check out the available commands in the documentation. However, you can always get a summary
of the commands by typing ``?`` in the client.

Control Plane Configuration
---------------------------
__ advanced_usage.html

Once that we have a working topology with configured P4 switches, we need to populate
the data plane with forwarding information in order to establish connectity. This can 
be done programmatically with a Python script or in a static way with the *Thrift*
client. The first method will be covered in the `advanced usage section`__, whereas the
second is explained below.

Thrift Client
+++++++++++++

Command Files
+++++++++++++