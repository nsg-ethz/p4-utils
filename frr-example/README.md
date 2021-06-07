# Topology
<p align ="center">
<img src="images/BGP.png" title="Network Topology">
<p/>

## Introduction

Super-Node based topologies for testing our integrated control plane and data plane node. Current topology comprises of 2 Autonomous Systems (AS), with the control plane routers 
spread across 2 AS, while the P4 switches are in the same logical network.




# Parser

The parser describes a state machine with one `start` state and two possible final states: `accept` 
or `reject`. Explain the basic state machine used to parse ethernet and ipv4, and explain that this 
can be used later to access those headers fields.