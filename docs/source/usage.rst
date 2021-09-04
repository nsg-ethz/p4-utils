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

JSON
++++

The JSON method is the legacy method for defining a network topology. It is based 
on the :py:class:`~p4utils.p4run.AppRunner`, a parser that reads the JSON files 
and creates a network accordingly.

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

Control Plane Configuration
---------------------------

Thrift Client
+++++++++++++

Command Files
+++++++++++++