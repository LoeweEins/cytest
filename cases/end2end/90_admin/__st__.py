import os
from cytest import INFO, GSTORE

force_tags = ['90_admin']

def suite_setup():
    INFO('[90_admin] suite_setup')

def suite_teardown():
    INFO('[90_admin] suite_teardown')
