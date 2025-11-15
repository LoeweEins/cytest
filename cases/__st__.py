from hytest import INFO,GSTORE
from lib.share import  gs

force_tags = ['功能测试']


def suite_setup():
    GSTORE.hello = 'hellooooooooooooooooooooooo'
    GSTORE['good'] = '333333333333333'
    gs.driver = 'abc'
    INFO('总初始化')


def suite_teardown():
    INFO('总清除')
    pass