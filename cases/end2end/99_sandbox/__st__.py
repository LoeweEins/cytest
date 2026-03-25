import os
from cytest import INFO, GSTORE

force_tags = ['99_sandbox']

def suite_setup():
    INFO('[99_sandbox] suite_setup')

def suite_teardown():
    INFO('[99_sandbox] suite_teardown')
