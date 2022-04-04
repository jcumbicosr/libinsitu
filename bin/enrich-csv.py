#!/usr/bin/env python

import os, sys
this_folder =  os.path.dirname(__file__)
sys.path.append(os.path.join(this_folder, ".."))

from libinsitu.cli.enrich_csv import main

if __name__ == '__main__':
    main()