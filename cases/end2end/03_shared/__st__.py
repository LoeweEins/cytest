import os
from cytest import INFO, GSTORE

force_tags = ['03_shared']

def suite_setup():
    INFO('[03_shared] suite_setup')

def suite_teardown():
    INFO('[03_shared] suite_teardown')
