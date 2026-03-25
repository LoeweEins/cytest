import os
from cytest import INFO, GSTORE

force_tags = ['50_payments']

def suite_setup():
    INFO('[50_payments] suite_setup')

def suite_teardown():
    INFO('[50_payments] suite_teardown')
