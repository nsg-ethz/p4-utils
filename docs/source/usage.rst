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
  that makes use of :py:class:`p4utils.mininetlib.network_API.NetworkAPI`,

- __ #json

  the `JSON method`__, on the other hand, relies on writing a JSON network
  definition file using the specifications of the parser 
  :py:class:`p4utils.p4run.AppRunner`.

Python
++++++

The Python method is a newly introduced feature that allows to programmatically
specify which elements are present in the network and how they are connected.
It is based on :py:class:`p4utils.mininetlib.network_API.NetworkAPI`, an API that
has a lot of methods to precisely define the network structure.

In order to define the network, we first need to import the required module and
create a ``NetworkAPI`` object::

    from p4utils.mininetlib.network_API import NetworkAPI

    net = NetworkAPI()

We can also set the level of details for the log shown during the execution of
the script::

    net.setLogLevel('info')

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

JSON
++++

Control Plane Configuration
---------------------------

Thrift Client
+++++++++++++

Command Files
+++++++++++++