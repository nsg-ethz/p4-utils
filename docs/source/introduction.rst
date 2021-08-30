Introduction
============

About P4-Utils
--------------

.. _Mininet: http://mininet.org/
.. _behavioral-model: https://github.com/p4lang/behavioral-model

P4-Utils is a Python package that allows the user to create and test virtual networks
that can include P4 switches. The network creation capabilities are inherited from Mininet_,
whereas the P4 targets are taken from the behavioral-model_.

The *behavioral-model* is a collection of P4 software switches. It is meant to be used as a 
tool for developing, testing and debugging P4 data planes and control plane software 
written for them. Indeed, P4 programmable hardware switches are still expensive
and operate them might still be somehow cumbersome.

*Mininet*, on the other hand, is a very powerful network emulation framework. Indeed, it can
efficiently virtualize nodes (hosts and switches) in a network by exploiting Linux kernel
features. This allows P4-Utils to create a realistic environment in which P4 switches can 
be connected together and tested.

P4 Language
-----------

*P4* is a domain-specific programming language that specifies how data plane devices
process packets. The key factor that makes it a very useful tool is that it has been 
designed to be *target-independent* (i.e. it can be used with a wide range of both 
hardware-based and software-based architecture) and *protocol-independent* (i.e. targets
are not bound to any specific network protocol).

Previous Work
-------------

.. _p4app: https://github.com/p4lang/p4app

The application p4app_ is the ancestor of P4-Utils: the former was created by the P4
community to provide a testing and prototyping platform based on P4 language, whereas the latter
is an adaptation made by the ETH Networked Systems Group to simplify the application use
and have a tool for P4 teaching.