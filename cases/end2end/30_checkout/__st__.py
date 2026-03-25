import os
from cytest import INFO, GSTORE

force_tags = ['30_checkout']

def suite_setup():
    INFO('[30_checkout] suite_setup')

def suite_teardown():
    INFO('[30_checkout] suite_teardown')
