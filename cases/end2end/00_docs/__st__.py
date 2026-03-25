import os
from cytest import INFO, GSTORE

force_tags = ['00_docs']

def suite_setup():
    INFO('[00_docs] suite_setup')

def suite_teardown():
    INFO('[00_docs] suite_teardown')
