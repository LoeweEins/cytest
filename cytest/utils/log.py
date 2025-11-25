# 用来定义日志相关的功能
# 最后写！
import logging, os, time, traceback, platform
import shutil
from logging.handlers import RotatingFileHandler


from rich.console import Console
from rich.theme import Theme

from hytest.product import version

from datetime import datetime

from hytest.common import GSTORE

from .runner import Collector
from ..cfg import l,Settings

os.makedirs('log',exist_ok=True)

# 日志文件
logger = logging.getLogger('my_logger') 
logger.setLevel(logging.DEBUG)

logFile = os.path.join('log','testresult.log')
handler = RotatingFileHandler(
    logFile, 
    maxBytes=1024*1024*30, 
    backupCount=2,
    encoding='utf8')
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(fmt='%(message)s')
handler.setFormatter(formatter)

handler.doRollover() # 每次启动创建一个新log文件，而不是从原来的基础上继续添加

logger.addHandler(handler)


# # 重定向stdout，改变print行为，同时写屏和日志
# import sys
# class MyPrintClass:
 
#     def __init__(self):
#         self.console = sys.stdout

#     def write(self, message):
#         self.console.write(message)
#         logger.info(message)
 
#     def flush(self):
#         self.console.flush()
#         # self.file.flush()

# sys.stdout = MyPrintClass()



console = Console(theme=Theme(inherit=False))

print = console.print



class LogLevel:
    """
    here, we use different log level numbers with Python logging lib
    CRITICAL - 0
    ERROR    - 1
    WARNING  - 2
    INFO     - 3
    DEBUG    - 4
    ALL      - 5
    """
    level = 3

