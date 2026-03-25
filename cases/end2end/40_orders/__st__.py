import os
from cytest import INFO, GSTORE

force_tags = ['40_orders']

def suite_setup():
    INFO('[40_orders] suite_setup')

def suite_teardown():
    INFO('[40_orders] suite_teardown')
