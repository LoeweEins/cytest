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




# 在命令行里用 rich 进行输出
class ConsoleLogger:
    
    def test_end(self, runner):
        ret = stats.result # stats的结果字典
        print((f'\n\n  ========= 测试耗时 : {stats.test_duration:.3f} 秒 =========\n',
               f'\n\n  ========= Duration Of Testing : {stats.test_duration:.3f} seconds =========\n')[l.n])


        print(f"\n  {('预备执行用例数量','number of cases plan to run')[l.n]} : {ret['case_count_to_run']}")

        print(f"\n  {('实际执行用例数量','number of cases actually run')[l.n]} : {ret['case_count']}")

        print(f"\n  {('通过','passed')[l.n]} : {ret['case_pass']}", style='green')
        
        num = ret['case_fail']
        style = 'white' if num == 0 else 'bright_red'
        print(f"\n  {('失败','failed')[l.n]} : {num}", style=style)
        
        num = ret['case_abort']
        style = 'white' if num == 0 else 'bright_red'
        print(f"\n  {('异常','exception aborted')[l.n]} : {num}", style=style)
        
        num = ret['suite_setup_fail']
        style = 'white' if num == 0 else 'bright_red'
        print(f"\n  {('套件初始化失败','suite setup failed')[l.n]} : {num}", style=style)
        
        num = ret['suite_teardown_fail']
        style = 'white' if num == 0 else 'bright_red'
        print(f"\n  {('套件清除  失败','suite teardown failed')[l.n]} : {num}", style=style)
        
        num = ret['case_setup_fail']
        style = 'white' if num == 0 else 'bright_red'
        print(f"\n  {('用例初始化失败','cases setup failed')[l.n]} : {num}", style=style)
        
        num = ret['case_teardown_fail']
        style = 'white' if num == 0 else 'bright_red'
        print(f"\n  {('用例清除  失败','cases teardown failed')[l.n]} : {num}", style=style)

        print("\n\n")
    
    # 只关心 file 级别，不关心 dir 级别
    def enter_suite(self,name,suitetype):   
        if suitetype == 'file' :
            print(f'\n\n>>> {name}',style='bold bright_white')

    
    def enter_case(self, caseId ,name, case_className):        
        print(f'\n* {name}',style='bright_white')

    
    def case_steps(self,name):...

    
    # def case_pass(self, case, caseId, name):
    #     print('                          PASS',style='green')

    
    # def case_fail(self, case, caseId, name, e, stacktrace):
    #     print(f'                          FAIL\n{e}',style='bright_red')
        
    
    # def case_abort(self, case, caseId, name, e, stacktrace):
    #     print(f'                          ABORT\n{e}',style='magenta')

    # 失败和 abort 都会抛出错误信息
    def case_result(self,case):
        if case.execRet == 'pass':
            print('                          PASS',style='green')
        elif case.execRet == 'fail':
            print(f'                          FAIL\n{case.error}',style='bright_red')
        elif case.execRet == 'abort':
            print(f'                          ABORT\n{case.error}',style='magenta')


    
    def setup_begin(self,name, utype):...
    
    
    def teardown_begin(self,name, utype):...


    # utype 可能是 suite  case  case_default
    def setup_fail(self,name, utype, e, stacktrace): 
        utype =  ('套件','suite')[l.n] if utype.startswith('suite') else ('用例','case')[l.n]
        print(f"\n{utype} {('初始化失败','setup failed')[l.n]} | {name} | {e}",style='bright_red')
        # print(f'\n{utype} setup fail | {name} | {e}',style='bright_red')

    
    def teardown_fail(self,name, utype, e, stacktrace):      
        utype =  ('套件','suite')[l.n] if utype.startswith('suite') else ('用例','case')[l.n]
        print(f"\n{utype} {('清除失败','teardown failed')[l.n]} | {name} | {e}", style='bright_red')
        # print(f'\n{utype} teardown fail | {name} | {e}',style='bright_red')


    def info(self, msg):
        if LogLevel.level >= 3:
            print(f'{msg}')

    def debug(self, msg):
        if LogLevel.level >= 4:
            print(f'{msg}')

    def error(self,msg):
        if LogLevel.level >= 1:
            print(f'{msg}', style='bright_red')


    def critical(self,msg):
        if LogLevel.level >= 0:
            print(f'{msg}', style='green')


class TextLogger:

    def test_start(self,_title=''):
        startTime = time.strftime('%Y%m%d_%H%M%S',
                                           time.localtime(stats.start_time))

        logger.info(f'\n\n  ========= {("测试开始","Test Start")[l.n]} : {startTime} =========\n')


    def test_end(self, runner):
        endTime = time.strftime('%Y%m%d_%H%M%S',
                                  time.localtime(stats.end_time))
        logger.info(f'\n\n  ========= {("测试结束","Test End")[l.n]} : {endTime} =========\n')

        logger.info(f"\n  {('耗时','Duration Of Testing ')[l.n]}    : {(stats.end_time-stats.start_time):.3f} 秒\n")
        ret = stats.result

        logger.info(f"\n  {('预备执行用例数量','number of cases plan to run')[l.n]} : {ret['case_count_to_run']}")
        logger.info(f"\n  {('实际执行用例数量','number of cases actually run')[l.n]} : {ret['case_count']}")
        logger.info(f"\n  {('通过','passed')[l.n]} : {ret['case_pass']}")
        logger.info(f"\n  {('失败','failed')[l.n]} : {ret['case_fail']}")
        logger.info(f"\n  {('异常','exception aborted')[l.n]} : {ret['case_abort']}")
        logger.info(f"\n  {('套件初始化失败','suite setup failed')[l.n]} : {ret['suite_setup_fail']}")
        logger.info(f"\n  {('套件清除  失败','suite teardown failed')[l.n]} : {ret['suite_teardown_fail']}")
        logger.info(f"\n  {('用例初始化失败','cases setup failed')[l.n]} : {ret['case_setup_fail']}")
        logger.info(f"\n  {('用例清除  失败','cases teardown failed')[l.n]} : {ret['case_teardown_fail']}")
    
    def enter_suite(self,name,suitetype): 
        logger.info(f'\n\n>>> {name}')

    
    def enter_case(self, caseId ,name , case_className):
        curTime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f'\n* {name}  -  {curTime}')

    
    def case_steps(self,name):  
        logger.info(f'\n  [ case execution steps ]')

    
    # def case_pass(self, case, caseId, name):
    #     logger.info('  PASS ')

    
    # def case_fail(self, case, caseId, name, e, stacktrace):
    #     logger.info(f'  FAIL   {e} \n{stacktrace}')
        
    
    # def case_abort(self, case, caseId, name, e, stacktrace):
    #     logger.info(f'  ABORT   {e} \n{stacktrace}')


    def case_result(self,case):
        if case.execRet == 'pass':
            logger.info('  PASS ')
        else:
            if case.execRet == 'fail':   
                # 这里输出了详细的 stacktrace 信息，但是console里只输出了 error 信息                 
                logger.info(f'  FAIL\n\n{case.stacktrace}')


            elif case.execRet == 'abort':
                logger.info(f'  ABORT\n\n{case.stacktrace}')



    
    def setup_begin(self,name, utype): 
        logger.info(f'\n[ {utype} setup ] {name}')
    
    
    def teardown_begin(self,name, utype): 
        logger.info(f'\n[ {utype} teardown ] {name}')

    
    def setup_fail(self,name, utype, e, stacktrace):  
        logger.info(f'{utype} setup fail | {e} \n{stacktrace}')

    
    def teardown_fail(self,name, utype, e, stacktrace):  
        logger.info(f'{utype} teardown fail | {e} \n{stacktrace}')

    
    def info(self, msg):
        if LogLevel.level >= 3:
            logger.info(f'{msg}')

    def debug(self, msg): 
        if LogLevel.level >= 4:
            logger.info(f'{msg}')

    def error(self,msg):
        if LogLevel.level >= 1:
            logger.info(f'{msg}')


    def critical(self,msg):
        if LogLevel.level >= 0:
            logger.info(f'{msg}')

    def step(self,stepNo,desc):
        logger.info((f'\n-- 第 {stepNo} 步 -- {desc} \n',
                     f'\n-- Step #{stepNo} -- {desc} \n',
                     )[l.n])

    def checkpoint_pass(self, desc):
        logger.info((f'\n** 检查点 **  {desc} ---->  通过\n',
                     f'\n** checkpoint **  {desc} ---->  pass\n'
                     )[l.n])
        
    def checkpoint_fail(self, desc, compareInfo):
        logger.info((f'\n** 检查点 **  {desc} ---->  !! 不通过!!\n',
                     f'\n** checkpoint **  {desc} ---->  !! fail!!\n'
                     )[l.n])
        logger.info(compareInfo)
    # 记录图片文件路径，真正的图片保存在 html 里
    def log_img(self,imgPath: str, width: str = None):
        logger.info(f'picture {imgPath}')



import json
from .runner import Runner, Collector
from .signal import signal


class VueReportLogger:
    """
    Vue 3 
    """

    def __init__(self):
        self._suite_tree = []
        self._suite_stack = []
        self._current_file_node = None
        self._current_case_node = None
        self._suite_events = []

    def enter_suite(self, name, suitetype):
        node = {
            "type": "suite_dir" if suitetype == "dir" else "suite_file",
            "name": name,
            "children": [],
            "events": [],
        }
        if self._suite_stack:
            self._suite_stack[-1]["children"].append(node)
        else:
            self._suite_tree.append(node)

        if suitetype == "dir":
            self._suite_stack.append(node)
        else:
            self._current_file_node = node
            if self._suite_stack:
                self._suite_stack[-1]["children"].append(node) if node not in self._suite_stack[-1]["children"] else None

    def setup_begin(self, name, utype): ...

    def setup_fail(self, name, utype, e, stacktrace):
        event = {"action": "setup", "utype": utype, "name": name,
                 "status": "fail", "error": str(e), "stacktrace": stacktrace}
        self._suite_events.append(event)

    def teardown_fail(self, name, utype, e, stacktrace):
        event = {"action": "teardown", "utype": utype, "name": name,
                 "status": "fail", "error": str(e), "stacktrace": stacktrace}
        self._suite_events.append(event)

    def enter_case(self, caseId, name, case_className):
        self._current_case_node = {
            "caseId": caseId,
            "className": case_className,
        }

    def test_start(self, _title=''):
        self._start_time = time.time()

    def test_end(self, runner):
        ret = stats.result
        case_count_to_run = ret['case_count_to_run']
        blocked = case_count_to_run - ret['case_pass'] - ret['case_fail'] - ret['case_abort']

        report_data = {
            "version": version,
            "title": Settings.report_title,
            "startTime": time.strftime('%Y/%m/%d %H:%M:%S', time.localtime(stats.start_time)),
            "endTime": time.strftime('%Y/%m/%d %H:%M:%S', time.localtime(stats.end_time)),
            "generateTime": time.strftime('%Y-%m-%d %H:%M:%S'),
            "duration": round(stats.test_duration, 3),
            "summary": {
                "case_count_to_run": case_count_to_run,
                "case_count": ret['case_count'],
                "case_pass": ret['case_pass'],
                "case_fail": ret['case_fail'],
                "case_abort": ret['case_abort'],
                "blocked": blocked,
                "suite_setup_fail": ret['suite_setup_fail'],
                "suite_teardown_fail": ret['suite_teardown_fail'],
                "case_setup_fail": ret['case_setup_fail'],
                "case_teardown_fail": ret['case_teardown_fail'],
            },
            "cases": [self._serialize_case(case) for case in Runner.case_list],
            "suiteEvents": self._suite_events,
            "lang": l.n,
        }

        base_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(base_dir, 'template_vue.html')

        if not os.path.exists(template_path):
            print(f"Error: 找不到模版文件 {template_path}", style='bright_red')
            return
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()

        json_str = json.dumps(report_data, ensure_ascii=False)
        final_html = template_content.replace('__REPORT_DATA__', json_str)

        timestamp = time.strftime('%Y%m%d_%H%M%S', time.localtime(stats.start_time))
        report_filename = f'vue_report_{timestamp}.html'
        report_path = os.path.join('log', report_filename)
        os.makedirs('log', exist_ok=True)

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(final_html)

        print(f"\n  Vue 报告已生成 : {report_path} \n", style='green')

        if Settings.auto_open_report:
            import platform as _plat
            try:
                if _plat.system().lower() == 'windows':
                    os.startfile(report_path)
                elif _plat.system().lower() == 'darwin':
                    os.system(f'open "{report_path}"')
            except:
                pass

    def _serialize_case(self, case):
        return {
            "id": getattr(case, "_caseId", str(id(case))),
            "name": getattr(case, "name", "未命名"),
            "className": type(case).__name__,
            "status": getattr(case, "execRet", "unknown"),
            "duration": round(getattr(case, "_case_duration", 0), 3),
            "stepsDuration": round(getattr(case, "_steps_duration", 0), 3),
            "setupDuration": round(getattr(case, "_setup_duration", 0), 3) if hasattr(case, "_setup_duration") else None,
            "teardownDuration": round(getattr(case, "_teardown_duration", 0), 3) if hasattr(case, "_teardown_duration") else None,
            "error": str(getattr(case, "error", "")) if hasattr(case, "error") else "",
            "stacktrace": getattr(case, "stacktrace", ""),
            "tags": getattr(case, "tags", []),
            "logs": getattr(case, "log_records", []),
            "beginTime": time.strftime('%m-%d %H:%M:%S', time.localtime(getattr(case, "_case_begin_time", 0))),
        }







from dominate.tags import *
# html 的标签，如 div、span、h1、table、tr、td

from dominate.util import raw
# 嵌入原始的 css 和 js 代码

from dominate import document
# 创建 html 文档

class HtmlLogger:

    def __init__(self):
        self.curEle = None # 执行到哪个元素

    
        # 保存一个  用例文件名 -> htmlDiv对象 的表，因为执行到用例文件清除的时候，要在 用例文件Div对象里面添加 该文件teardown的子节点Div
        # 用例文件名 对应 div 对象的映射表
        self.suiteFileName2DivTable = {}
        

    # 开始构建 html 
    def test_start(self,_title=''):

        # 设置路径为 log.py 所在目录
        libDir = os.path.dirname(__file__)
        
        with open(os.path.join(libDir , 'report.css'), encoding='utf8') as f:
            _css_style = f.read() # os.path.join() 用来拼接路径
      
        with open(os.path.join(libDir , 'report.js'), encoding='utf8') as f:
            _js = f.read()   # js file

        

        self.doc = document(title= Settings.report_title)
        self.doc.head.add(
                        meta(charset="UTF-8"), # 两个 meta，元信息
                        meta(name="viewport", content="width=device-width, initial-scale=1.0"),
                        
                        
                        link(rel='icon', type="image/png" , href=os.path.join(libDir, 'icon.png')),
                        
                        style(raw(_css_style)),
                        script(raw(_js), type='text/javascript')
                        )

        self.main = self.doc.body.add(div(_class='main_section')) # 主容器

        self.main.add(h1(f'{Settings.report_title}', style='font-family: auto'))

        self.main.add(h3(('统计结果','Test Statistics')[l.n])) 

        resultDiv = self.main.add(div(_class='result')) # 主容器内

        self.result_table, self.result_barchart = resultDiv.add(
            table(_class='result_table'),
            div(_class='result_barchart')
        ) # 在 result 容器内加 table 和 柱状图 div

        
        _, self.logDiv = self.main.add(
            div(
                # span('切换到精简模式',_class='h3_button', id='display_mode' ,onclick="toggle_folder_all_cases()"), 
                h3(('执行日志','Test Execution Log')[l.n],style='display:inline'),
                style='margin-top:2em'
            ),
            div(_class='exec_log')
        )


        # 查看上一个和下一个错误的 
        # 没有在main里面，因为 main 是滚动区域
        self.ev = div(
                div('∧', _class = 'menu-item', onclick="previous_error()", title='上一个错误'), 
                div('∨', _class = 'menu-item', onclick="next_error()", title='下一个错误'),
                _class = 'error_jumper'
            )

        helpLink = ('https://github.com//LoeweEins/cytest/Documentation.md')
         
        # 加了一个 悬浮 div
        self.doc.body.add(div(
            div(('页首','Home')[l.n], _class = 'menu-item',
                onclick='document.querySelector("body").scrollIntoView()'),

            div(('帮助','Help')[l.n], _class = 'menu-item', 
                onclick=f'window.open("{helpLink}", "_blank"); '),

            div(('Summary','Summary')[l.n],_class='menu-item', id='display_mode' ,onclick="toggle_folder_all_cases()"),
            self.ev,
            id='float_menu')
        )

        # 初始化一些指针
        self.curEle = self.main  # 记录当前所在的 html element
        self.curSuiteEle = None   # 记录当前的套件元素
        self.curCaseEle = None   # 记录当前的用例元素
        self.curCaseLabelEle = None   # 记录当前的用例里面的 种类标题元素
        self.curSetupEle = None   # 记录当前的初始化元素
        self.curTeardownEle = None   # 记录当前的清除元素
        self.suitepath2element = {}


    
    def test_end(self, runner):

        execStartTime = time.strftime('%Y/%m/%d %H:%M:%S',
                                           time.localtime(stats.start_time))
        execEndTime = time.strftime('%Y/%m/%d %H:%M:%S',
                                           time.localtime(stats.end_time))

        ret = stats.result

        errorNum = 0

        trs = [] # table rows 列表  
        
        trs.append(tr(td(('cytest 版本','cytest version')[l.n]), td(version)))
        trs.append(tr(td(('开始时间','Test Start Time')[l.n]), td(f'{execStartTime}')))
        trs.append(tr(td(('结束时间','Test End Time')[l.n]), td(f'{execEndTime}')))

        trs.append(tr(td(('耗时','Duration Of Testing')[l.n]), td(f'{stats.test_duration:.3f}' + (' 秒',' Seconds')[l.n])))

        trs.append(tr(td(('预备执行用例数量','number of cases plan to run')[l.n]), td(f"{ret['case_count_to_run']}")))
        trs.append(tr(td(('实际执用例行数量','number of cases actually run')[l.n]), td(f"{ret['case_count']}")))

        trs.append(tr(td(('通过','passed')[l.n]), td(f"{ret['case_pass']}")))


        case_count_to_run = ret['case_count_to_run']

        # 计算失败用例个数
        num = ret['case_fail']
        style = '' if num == 0 else 'color:red'
        trs.append(tr(td(('失败','failed')[l.n]), td(f"{num}", style=style)))
        errorNum += num
        
        # 计算异常用例个数
        num = ret['case_abort']
        style = '' if num == 0 else 'color:red'
        trs.append(tr(td(('异常','exception aborted')[l.n]), td(f"{num}", style=style)))
        errorNum += num

        # 计算阻塞用例个数
        blocked_num = case_count_to_run - ret['case_pass'] - ret['case_fail'] - ret['case_abort']
        style = '' if blocked_num == 0 else 'color:red'
        trs.append(tr(td(('阻塞','blocked')[l.n]), td(f"{blocked_num}", style=style)))
        
        # 计算suite初始化失败次数
        num = ret['suite_setup_fail']
        style = '' if num == 0 else 'color:red'
        trs.append(tr(td(('套件初始化失败','suite setup failed')[l.n]), td(f"{num}", style=style)))
        errorNum += num
        
        # 计算suite清除失败次数
        num = ret['suite_teardown_fail']
        style = '' if num == 0 else 'color:red'
        trs.append(tr(td(('套件清除  失败','suite teardown failed')[l.n]), td(f"{num}", style=style)))
        errorNum += num
        
        # 计算case初始化失败次数
        num = ret['case_setup_fail']
        style = '' if num == 0 else 'color:red'
        trs.append(tr(td(('用例初始化失败','cases setup failed')[l.n]), td(f"{num}", style=style)))
        errorNum += num
        
        # 计算case清除失败次数
        num = ret['case_teardown_fail']
        style = '' if num == 0 else 'color:red'
        trs.append(tr(td(('用例清除  失败','cases teardown failed')[l.n]), td(f"{num}", style=style)))
        errorNum += num


        # 没有error，隐藏错误跳转
        self.ev['display'] = 'none' if errorNum==0 else 'block'

        # 添加结果统计表
        # tbody 用于包裹 tr 列表
        self.result_table.add(tbody(*trs))



        # 添加 结果柱状图
        def add_barchar_item(statName, percent, color):
            if type(percent) == str:
                barPercentStr = percent
                percentStr ='-'

            else:
                # 小于 1% 的， 都显示 1% 长度，否则就看不见了
                barPercent = 1 if 0 < percent <= 1 else percent

                barPercentStr = f'{barPercent}%'
                percentStr = f'{percent}%'

            self.result_barchart.add(
                div(
                    span(statName),
                    div(
                        div(
                            "" , # 柱状里面不填写内容了，如果值为1.86%,背景色部分太短，由于颜色是白色，溢出到右边的空白背景，看不清
                            style=f'width: {barPercentStr}; background-color: {color};',
                            _class="barchart_bar",
                        ),
                        _class="barchart_barbox"
                    ),
                    _class="barchar_item"
                )
            )

        # add_barchar_item(
        #     f"用例总数 ： {ret['case_count']} 个",
        #     100,
        #     '#2196f3')



        # 计算比例
        def percentCalc(upper: int, lower: int) -> str:
            percent = str(round(upper * 100 / lower, 1)) # 取一位小数 + '%'
            percent = percent[:-2] if percent.endswith('.0') else percent
            return percent

        percent = percentCalc(ret['case_pass'], case_count_to_run)
        add_barchar_item(
            f"{('用例通过','cases passed')[l.n]} {percent}% ： {ret['case_pass']} {('个','')[l.n]}",
            float(percent),
            '#04AA6D')

        percent = percentCalc(ret['case_fail'], case_count_to_run)
        add_barchar_item(
            f"{('用例失败','cases failed')[l.n]} {percent}% ： {ret['case_fail']} {('个','')[l.n]}",
            float(percent),
            '#bb4069')

        percent = percentCalc(ret['case_abort'], case_count_to_run)
        add_barchar_item(
            f"{('用例异常','cases exception aborted')[l.n]} {percent}% ： {ret['case_abort']} {('个','')[l.n]}",
            float(percent),
            '#9c27b0')


        percent = percentCalc(blocked_num, case_count_to_run)
        add_barchar_item(
            f"{('用例阻塞','cases blocked')[l.n]} {percent}% ： {blocked_num} {('个','')[l.n]}",
            float(percent),
            '#dcbdbd')

        # st_fail = ret['suite_setup_fail'] + ret['case_setup_fail'] + ret['suite_teardown_fail'] + ret['case_teardown_fail']
        # percent = '100%' if st_fail > 0 else '0%'
        # add_barchar_item(
        #     f"初始化/清除 失败  {st_fail} 次",
        #     percent,
        #     '#dcbdbd')


        # 生成 html
        htmlcontent = self.doc.render()

        # 用时间戳命名 html 报告文件
        timestamp = time.strftime('%Y%m%d_%H%M%S',time.localtime(stats.start_time))
        fileName = f'report_{timestamp}.html'
        reportPath = os.path.join('log',fileName)
        with open(reportPath,'w',encoding='utf8') as f:
            f.write(htmlcontent)


        #  with command line parameter report_url_prefix
        #  need to copy report from dir 'log' to 'reports'
        # 服务器运行，通过 report_url_prefix 指定 URL 前缀
        if Settings.report_url_prefix:
            os.makedirs('reports', exist_ok=True)
            cpTargetPath = os.path.join('reports',fileName)
            shutil.copyfile(reportPath, cpTargetPath)
            o1 = ('测试报告','test report')[l.n]
            print(f"{o1} : {Settings.report_url_prefix}/{fileName} \n")




    # 进入用例目录 或者 用例文件
    def enter_suite(self,name: str,suitetype: str): 
        _class = 'suite_' + suitetype # 有 dir  file 两种类型

        enterInfo = ('进入目录','Enter Folder')[l.n] if suitetype == 'dir' \
                else ('进入文件','Enter File')[l.n]
        
        self.curEle = self.logDiv.add(
            div(                
                div(
                    span(enterInfo,_class='label'),
                    span(name),
                    _class='enter_suite'
                ),         
                _class=_class, id=f'{_class} {name}'
            )
        )
        self.curSuiteEle = self.curEle
        self.curSuiteFilePath = name

        self.suitepath2element[name] = self.curEle
             
    
    # 进入case时创建大的 case 元素，包含 label、name、time、duration、body
    # 其中 body 是单独的一个 div，可以折叠隐藏
    def enter_case(self, caseId ,name, case_className):       
        
        # 执行有结果后，要修改这个 self.curCaseLabelEle ，比如 追加 PASS
        self.curCaseLabelEle = span(('用例','Case')[l.n],_class='label caselabel')
        self.caseDurationSpan = span("", _class='duration')
        self.curCaseBodyEle = div(
            span(f'{self.curSuiteFilePath}::{case_className}', _class='case_class_path') , 
            _class='folder_body') # folder_body 是折叠区 内容部分，可以隐藏
            # 并且这个CaseBody里面还会添加 setup、teardown、steps 等元素

        self.curCaseEle = self.curSuiteEle.add(
            div(
                div(
                    self.curCaseLabelEle,
                    span(name, _class='casename'),
                    span(datetime.now().strftime('%m-%d %H:%M:%S'), _class='executetime'),
                    self.caseDurationSpan,
                    _class='folder_header'
                ),
                self.curCaseBodyEle ,
                _class='case',id=f'case_{caseId:08}'
               )
        )
        self.curEle = self.curCaseBodyEle


    # 离开case时加上时间
    def leave_case(self, caseId, duration):
        self.caseDurationSpan += f"{round(duration,1)}s"
    

    # 用例步骤开始，加在 CaseBody 里面
    # 这是一个 label 级别的元素
    def case_steps(self,name):
        self.stepsDurationSpan = span("", _class='duration')
        ele = div(
                div(
                    span(('测试步骤','Test Steps')[l.n], _class='label'),
                    self.stepsDurationSpan,
                    _class="flow-space-between",
                ),
            _class='test_steps', id='test_steps ' + name)
        
        self.curEle = self.curCaseBodyEle.add(ele)

    
    # def case_pass(self, case, caseId, name): 
    #     self.curCaseEle['class'] += ' pass'
    #     self.curCaseLabelEle += ' PASS'
    
    # def case_fail(self, case, caseId, name, e, stacktrace):
        
    #     self.curCaseEle['class'] += ' fail'
    #     self.curCaseLabelEle += ' FAIL'

    #     self.curEle += div(f'{e} \n{stacktrace}', _class='info error-info')
        
    
    # def case_abort(self, case, caseId, name, e, stacktrace):
        
    #     self.curCaseEle['class'] += ' abort'
    #     self.curCaseLabelEle += ' ABORT'

    #     self.curEle += div(f'{e} \n{stacktrace}', _class='info error-info')


    def case_result(self, case):
        if case.execRet == 'pass':
            self.curCaseEle['class'] += ' pass'
            self.curCaseLabelEle += ' ✅'

        elif case.execRet == 'fail':
            self.curCaseEle['class'] += ' fail'
            self.curCaseLabelEle += ' ❌'
            self.curEle += div(f'{case.stacktrace}', _class='info error-info')
            
        elif case.execRet == 'abort':                
            self.curCaseEle['class'] += ' abort'
            self.curCaseLabelEle += ' 🚫'
            self.curEle += div(f'{case.stacktrace}', _class='info abort-info')

        self.stepsDurationSpan += f"{round(case._steps_duration,1)}s"
            
    # utype 可能是 suite  case  case_default
    def setup_begin(self, name, utype):
        
        _class = f'{utype}_setup setup'

        self.setupDurationSpan = span("", _class='duration')
                     
        # 套件 setup
        if utype.startswith('suite_'):
            
            # folder_body 是折叠区 内容部分，可以隐藏
            suiteHeaderEle = div(
                span(('套件初始化','Suite Setup')[l.n],_class='label'),
                span(''),  #span(name),
                span(datetime.now().strftime('%m-%d %H:%M:%S'), _class='executetime'),

                self.setupDurationSpan,
                _class='folder_header')
            
            self.curSuiteHeaderEle = suiteHeaderEle
            
            stBodyEle = self.curEle = div(_class='folder_body')
            
            self.curSetupEle = div(
                suiteHeaderEle,
                stBodyEle,
                _class=_class,
                id=f'{_class} {name}')   

            self.curSuiteEle.add(self.curSetupEle)  

        # 用例 setup
        else:
            
            self.curSetupEle = self.curEle = div(
                div(
                    span(('用例初始化','Case Setup')[l.n],_class='label'),
                    self.setupDurationSpan,
                    _class="flow-space-between",
                ),
                _class=_class,
                id=f'{_class} {name}')

            self.curCaseBodyEle.add(self.curSetupEle)
            self.curEle['class'] += ' case_st_label'
    
            
    # utype 可能是 suite  case  case_default
    def setup_end(self, name, utype, duration): 

        self.setupDurationSpan += f"{round(duration,1)}s"



        
    # utype 可能是 suite  case  case_default
    def teardown_begin(self,name, utype): 

        _class = f'{utype}_teardown teardown'

        self.teardownDurationSpan = span("", _class='duration')

        # 套件 teardown
        if utype.startswith('suite_'):    

            # 是套件目录的清除，创建新的 curSuiteEle
            if utype == 'suite_dir':
                        
                self.curEle = self.logDiv.add(
                    div(                
                        div(
                            span(('离开目录','Leave Folder')[l.n] ,_class='label'),
                            span(name),
                            _class='leave_suite'
                        ),         
                        _class="suite_dir", id=f'{_class} {name}'
                    )
                )
                self.curSuiteEle = self.curEle
            
            # folder_body 是折叠区 内容部分，可以隐藏
            suiteHeaderEle = div(
                span(('套件清除','Suite Teardown')[l.n],_class='label'),
                span(''),  #span(name),
                span(datetime.now().strftime('%m-%d %H:%M:%S'), _class='executetime'),
                self.teardownDurationSpan,
                _class='folder_header')
            
            stBodyEle = self.curEle = div(_class='folder_body')
            
            self.curTeardownEle = div(
                suiteHeaderEle,
                stBodyEle,
                _class=_class,
                id=f'{_class} {name}')   

            self.curSuiteEle.add(self.curTeardownEle)

        # 用例 teardown
        else:            
            self.curTeardownEle = self.curEle = div(                
                div(
                    span(('用例清除','Case Teardown')[l.n],_class='label'),
                    self.teardownDurationSpan,
                    _class="flow-space-between",
                ),
                _class=_class,
                id=f'{_class} {name}')

            self.curCaseBodyEle.add(self.curTeardownEle)
            self.curEle['class'] += ' case_st_label'


    # utype 可能是 suite  case  case_default
    def teardown_end(self, name, utype, duration): 
        self.teardownDurationSpan += f"{round(duration,1)}s"

    
    def setup_fail(self,name, utype, e, stacktrace):  
        self.curSetupEle['class'] += ' fail'
        self.curEle += div(f'{utype} setup fail | {e} \n{stacktrace}', _class='info error-info')
    
    def teardown_fail(self,name, utype, e, stacktrace):           
        self.curTeardownEle['class'] += ' fail'
        self.curEle += div(f'{utype} teardown fail | {e} \n{stacktrace}', _class='info error-info')

    def info(self, msg):
        msg = f'{msg}'
        if self.curEle is None:
            return

        self.curEle += div(msg, _class='info')


    def step(self,stepNo,desc):
        if self.curEle is None:
            return

        self.curEle += div(span(f'{("步骤","Step")[l.n]} #{stepNo}', _class='tag'), span(desc), _class='case_step')

    def checkpoint_pass(self, desc):
        if self.curEle is None:
            return

        self.curEle += div(span(f'{("检查点","CheckPoint")[l.n]} ✅', _class='tag'), 
                           span(desc, _class='paragraph' ), 
                           _class='checkpoint_pass')
        
    def checkpoint_fail(self, desc, compareInfo):
        if self.curEle is None:
            return

        self.curEle += div(span(f'{("检查点","CheckPoint")[l.n]} ❌', _class='tag'), 
                           span(f"{desc}\n\n{compareInfo}" , _class='paragraph' ), 
                           _class='checkpoint_fail')


    def log_img(self,imgPath: str, width: str = None):
        if self.curEle is None:
            return

        self.curEle += div(img(src=imgPath, width= '50%' if width is None else width, _class='screenshot' ))



from .signal import signal

signal.register([
    stats,
    ConsoleLogger(), 
    TextLogger(),
    VueReportLogger(), 
    HtmlLogger()])