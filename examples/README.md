# Examples

This directory collects some working examples that make use of *P4-Utils*. In particular we have the following subfolders, each one containing a specific topology.

- [switches](./switches): topology including only `P4Switches`. The goal of this example is ensuring L2 and L3 connectivity among hosts.
- [frrouters](./frrouters): topology including `P4Switches` and `FRRouters`. The goal is ensuring L2 and L3 connectivity among hosts, considering also different ASes.
- [adv-net](./adv-net): topology including both `P4Switches` and `FRRouter` used in the *Advanced Topics in Communication Networks* 2020 project. It is not fully functional for what concerns *Traffic Control*.