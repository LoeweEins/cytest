import os
from cytest import INFO, GSTORE

force_tags = ['22_product']

def suite_setup():
    INFO('[22_product] suite_setup')

def suite_teardown():
    INFO('[22_product] suite_teardown')
