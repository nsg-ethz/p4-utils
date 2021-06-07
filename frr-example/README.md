# Implementing Basic Forwarding

```
                   +--+
                   |h4|
                   ++-+
                    |
                    |
+--+      +--+     ++-+     +--+
|h1+------+s1+-----+s3+-----+h3|
+--+      +-++     +--+     +--+
            |
            |
          +-++
          |s2|
          +-++
            |
            |
          +-++
          |h2|
          +--+
```

## Introduction

Super-Node based topologies for testing our integrated control plane and data plane node. Current topology comprises of 2 Autonomous Systems (AS), with the control plane routers 
spread across 2 AS, while the P4 switches are in the same logical network.

<img width="964" alt = "java" src="/p4-utils/frr-example/images/BGP.png">

# Parser

The parser describes a state machine with one `start` state and two possible final states: `accept` 
or `reject`. Explain the basic state machine used to parse ethernet and ipv4, and explain that this 
can be used later to access those headers fields.