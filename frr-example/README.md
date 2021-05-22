# Fundamental network operations

![Network topology](./images/ffr_example_topo.png "Network topology")

## Introduction

The objective of this example is to provide an overview of the capabilities of **p4-utils**. According to the topology above, we have 2 ASes. AS 1 is responsible for the prefix `1.0.0.0/8`, while AS 2 `2.0.0.0/8`. In each one of them we have serveral hosts, routers and P4 switches. The goal is using all the main protocols and technologies to gain full connectivity among the hosts. In particular, this involves the following:
- *L2 learning* for P4 switches, in order to have L2 connectivity within each network segment;
- *OSPF* for routers, in order to have connectivity within the same AS;
- *BGP* for routers, in order to have connectivity among different ASes;
- *LDP* for routers, in order to make the core of AS 1 (R3) *BGP*-free and still having full connectivity.

## Execution

The scenario can be executed with both the following commands:
```
sudo p4run
```
or
```
sudo python network.py
```

Please notice that *OSPF*, *LDP* and *BGP* take some time to converge, so at the beginning the network can still be partitioned.