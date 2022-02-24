# Heavy hitter with tofino model switches

You can use p4-utils to start the topology with Tofino switches and hosts. As 
first parameter you have to set the path to the SDE.

```
# start network
sudo python network.py <SDE PATH>

# controller code
mx s1 
$SDE/run_bfshell.sh -b `pwd`/controller_1.py

# controller code
mx s2
$SDE/run_bfshell.sh -b `pwd`/controller_2.py

# start receiver
mx h2
python receive.py

# send 1500 packets, and observe how only 1000 are received
mx h1 
python send.py 10.2.2.2 1500
```

