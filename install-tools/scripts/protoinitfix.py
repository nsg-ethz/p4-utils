#!/usr/bin/env python3
# This scripts creates a __init__.py file in the main directory of
# the google module if it is not present already. Indeed the lack of such
# file prevent sphinx from working correctly.

import os
import re
import google


path = re.findall(r"\['(.*)'\]", str(google.__path__))[0]
init_file = os.path.join(path, '__init__.py')

# If __init__.py is not present in the google module directory
if not os.path.isfile(init_file):
    # Create __init__.py file
    with open(init_file, 'w') as f:
        pass
    print('File {} correctly created.'.format(init_file))
else:
    print('File {} already present.'.format(init_file))