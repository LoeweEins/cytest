import os
from cytest import INFO, GSTORE

force_tags = ['01_smoke']

def suite_setup():
    INFO('[01_smoke] suite_setup')

def suite_teardown():
    INFO('[01_smoke] suite_teardown')
