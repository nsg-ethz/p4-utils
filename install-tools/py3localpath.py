#!/usr/bin/env python3
# Modified from https://github.com/jafingerhut/p4-guide/blob/master/bin/py3localpath.py

import re
import sys

l1=[x for x in sys.path if re.match(r'/usr/local/lib/python3.[0-9]+/dist-packages$', x)]

if len(l1) == 1:
    m = re.match(r'(/usr/local/lib/python3.[0-9]+)/dist-packages$', l1[0])
    if m:
        print(m.group(1))
    else:
        print("Inconceivable!  Somehow the second pattern did not match but the first did.")
        sys.exit(1)
else:
    print("Found %d matching entries in Python3 sys.path instead of 1: %s"
          % (len(l1), l1))
    sys.exit(1)

sys.exit(0)