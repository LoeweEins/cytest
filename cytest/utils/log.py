# 用来定义日志相关的功能
# 最后写！
import logging, os, time, traceback, platform
import shutil
from logging.handlers import RotatingFileHandler


from rich.console import Console
from rich.theme import Theme

from cytest.product import version
from datetime import datetime
from cytest.common import GSTORE

from .runner import Collector
from ..cfg import l,Settings
# logging 官方日志模块
# os 处理路径
# time 处理时间
# traceback 处理异常堆栈
# platform 获取系统信息(操作系统，python版本)

# shutil 文件复制、移动、压缩
# logging.handlers.RotatingFileHandler 日志文件按大小切割

# rich.console.Console 美化控制台输出
# rich.theme.Theme 定制 rich 颜色主题

# datetime 时间格式化，如20250130_151022

os.makedirs('log',exist_ok=True)

# 日志文件
logger = logging.getLogger('my_logger') # 日志器的名字是 my_logger
logger.setLevel(logging.DEBUG) # 最低级别，debug以上都记录
logFile = os.path.join('log','testresult.log')

# 日志处理器，按大小切割
# 日志太大，滚动生成 testresult.log.1、testresult.log.2
handler = RotatingFileHandler(
    logFile, 
    maxBytes=1024*1024*30, # 30MB，超过自动切割
    backupCount=2,# 最多保留 2 个旧日志文件
    encoding='utf8'
)

handler.setLevel(logging.DEBUG)

# 日志格式器，只记录消息内容
formatter = logging.Formatter(fmt='%(message)s')
handler.setFormatter(formatter)

handler.doRollover() # 每次启动创建一个新log文件，而不是从原来的基础上继续添加

logger.addHandler(handler)
# 设置 handler 和 formatter，逐层绑定


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


# 使用 rich 定义控制台输出
# 覆盖原来的 print 方法
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


# Stats 测试统计核心
class Stats:

    # 测试开始，初始化一大堆
    def test_start(self,_title='Test Report'):
        self.result = {
            # 这是准备执行的用例数量
            'case_count_to_run': Collector.case_number,
            # 这个是实际执行的用例数量，可能有其他的用例因为初始化失败没有执行
            'case_count' : 0,
            'case_pass'  : 0,
            'case_fail'  : 0,
            'case_abort' : 0,
            'suite_setup_fail' : 0,
            'case_setup_fail' : 0,
            'suite_teardown_fail' : 0,
            'case_teardown_fail' : 0,
            'case_pass_list'  : [],
            'case_fail_list'  : [],
            'case_abort_list' : [],

        }
                
    
        self.start_time = time.time()

    def test_end(self, runner):
        self.end_time = time.time()
        self.test_duration = self.end_time-self.start_time

        if  self.result['case_fail'] or \
            self.result['case_abort'] or \
            self.result['suite_setup_fail'] or \
            self.result['case_setup_fail'] or \
            self.result['suite_teardown_fail'] or \
            self.result['case_teardown_fail'] :
            GSTORE['---ret---'] = 1
        else:
            GSTORE['---ret---'] = 0


    # 进入用例，case_count + 1
    def enter_case(self, caseId ,name, case_className):
        self.result['case_count'] += 1    
    

    # 根据 execRet，写 case_pass、case_fail、case_abort
    def case_result(self,case):
        if case.execRet == 'pass':
            self.result['case_pass'] += 1   
        elif case.execRet == 'fail':
            self.result['case_fail'] += 1  
        elif case.execRet == 'abort':
            self.result['case_abort'] += 1   


    # utype 可能是 suite  case  case_default     
    def setup_fail(self,name, utype, e, stacktrace):  
        if utype.startswith('suite'):
            self.result['suite_setup_fail'] += 1   
        else:
            self.result['case_setup_fail'] += 1 
    
    def teardown_fail(self,name, utype, e, stacktrace):  
        if utype.startswith('suite'):
            self.result['suite_teardown_fail'] += 1   
        else:
            self.result['case_teardown_fail'] += 1 

stats = Stats()