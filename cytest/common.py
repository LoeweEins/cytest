# checked
# 定义了一些全局变量，在 cytest 的__init__.py 中导入到包顶层 
# 供各模块使用
from .utils.signal import signal
from .utils.runner import Runner, CheckPointFail
from .cfg import l

import time
from datetime import datetime
import inspect # 获取CHECK_POINT()行的运行环境，变量、源代码、调用栈
import executing # 找到这行代码在Python内部 语法树 中的节点
import ast # 分析表达式结构，提取左右两边的内容，反解析成字符串

'''
功能
定义 GSTORE
定义 INFO() STEP() CHECK_POINT() LOG_IMG() SELENIUM_LOG_SCREEN()
与Runner、signal 交互
提供UI报告 表达式解析、左右值显示、失败原因

INFO("登录成功")
STEP(1,"输入用户名")
CHECK_POINT("检查登录是否成功", response.status_code==200 )
'''


'''
CHECK_POINT("检查登录", response.code == 200)
↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
Call
 ├── func: CHECK_POINT
 └── args:
      ├── Str("检查登录")
      └── Compare
            ├── left: Attribute(response.code)
            ├── op: Eq
            └── right: Constant(200)

AST：表示 代码结构和语义内容的 语法树


ast.Compare() 节点结构：
.left 左表达式
.ops 比较符号
.comparators 右表达式列表 

frame：当前代码运行时的执行环境
f_back：它的前一个调用者，就是call
f_code：函数的代码对象
f_locals：函数的局部变量
f_globals：全局变量
f_lineno：当前执行的代码行号
f_back：上一帧
'''










class _GlobalStore(dict): # 继承自 dict
    
    # print(GSTORE.a)
    def __getattr__(self, key, default=None):
        if key not in self:
            return default
        return self[key]
    
    # GSTORE.a = 123
    def __setattr__(self, key, value):
        self[key] = value
    
    # del GSTORE.a
    def __delattr__(self, key):
        if key not in self:
            return
        del self[key]

    # GSTORE['a']
    def __getitem__(self, key, default=None):
        return self.get(key, default)  

# used for storing global shared data
GSTORE = _GlobalStore()

def INFO(*args, sep=' ', end='\n'):
    """
    print information in log and report.
    This will not show in terminal window.

    Parameters
    ----------
    args : objects to print
    sep  : the char to join the strings of args objects, default is space char
    end  : the end char of the content, default is new line char.
    """
    # 把输入的 args 拼成 str 写进 log
    logStr = sep.join([str(arg) for arg in args]) + end
    # 通过 signal 发送 info 信号
    signal.info(logStr)

    # !!!!!!!!!!!!!!!!!!新增功能：保存到当前用例对象的 log_records 属性中 !!!!!!!!!!!!!!!!!!
    if Runner.curRunningCase:
        Runner.curRunningCase.log_records.append({
            "type": "info",
            "content": logStr.strip(),
            "timestamp": time.time()
        })

def STEP(stepNo:int,desc:str):
    """
    print information about test steps in log and report .
    This will not show in terminal window.


    Parameters
    ----------
    stepNo : step number
    desc :   description about this step
    """
    signal.step(stepNo,desc)
    if Runner.curRunningCase:
        Runner.curRunningCase.log_records.append({
            "type": "step",
            "step_no": stepNo,
            "description": desc,
            "timestamp": time.time()
        })


# 比较操作符映射表
# 用于反向解析，显示比较表达式的左右值
# AST 节点类型 到 操作符字符串 的映射
OP_MAP = {
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Is: "is",
    ast.IsNot: "is not",
    ast.In: "in",
    ast.NotIn: "not in",
}



def CHECK_POINT(desc:str, condition, failStop=True, failLogScreenWebDriver = None):
    """
    check point of testing.
    pass or fail of this check point depends on argument condition is true or false.
    it will print information about check point in log and report.

    Parameters
    ----------
    desc :    check point description, like check what.
    condition : usually it's a bool expression, like  `a==b`, 
        so actually, after evaluating the expression, it's a result bool object passed in .
    failStop : switch for whether continue executing test case when the condition value is false 
    failLogScreenWebDriver : Selenium web driver object,
        when you want a screenshot image of browser in test report if current check point fail.
    """

    # !!!!!!!!!!!!!!!!无论成功失败，先记录数据!!!!!!!!!!!!!!!!
    status = "pass" if condition else "fail"
    if Runner.curRunningCase:
        Runner.curRunningCase.log_records.append({
            "type": "checkpoint",
            "status": status,
            "content": desc,
            "timestamp": time.time()
        })


    # ✅  check point pass
    if condition:
        signal.checkpoint_pass(desc)
        return
    
    # ❌  check point fail
    try:
        # 获取调用帧，inspect 模块
        caller_frame = inspect.currentframe().f_back

        # 从调用帧处，获取调用节点，也就是call节点，用 executing
        ex = executing.Source.executing(caller_frame)
        call_node = ex.node

        compareInfo = ''
        
        # 确保拿到了一个调用节点，也就是 call 节点，用 ast 模块判断
        if isinstance(call_node, ast.Call):

            arg_node = call_node.args[1]

            # 如果是比较运算符
            if isinstance(arg_node, ast.Compare):                

                # * 反解析参数节点以获得完整表达式 ➡️🔍💲⬅️❌ 🔔💡 *
                full_expression_str = ast.unparse(arg_node).strip()
                compareInfo += (f" 🔎 {full_expression_str} ")

                left_expr_str = ast.unparse(arg_node.left).strip()
                right_expr_str = ast.unparse(arg_node.comparators[0]).strip()

                # op_node = arg_node.ops[0]
                # op_str = OP_MAP.get(type(op_node), "未知比较操作符")

                caller_globals = caller_frame.f_globals # 调用帧的全局变量
                caller_locals = caller_frame.f_locals # 调用帧的局部变量

                #全局和局部变量都要传入 eval 表达式中
                left_val = eval(left_expr_str, caller_globals, caller_locals)
                right_val = eval(right_expr_str, caller_globals, caller_locals)

                # repr 显示原始数据形式
                left_expr_value = repr(left_val)
                right_expr_value = repr(right_val)
                
                left_expr_value = left_expr_value if len(left_expr_value) < 2000 else f"{left_expr_value} ..."
                right_expr_value = right_expr_value if len(right_expr_value) < 2000 else f"{right_expr_value} ..."

                compareInfo += (f"\n 💲 {('左边','left  ')[l.n]} 🟰 {left_expr_value}")
                # print(f"💡 {op_str}")
                compareInfo += (f"\n 💲 {('右边','right ')[l.n]} 🟰 {right_expr_value}")

        else:
            print(("⚠️  无法获取 CHECK_POINT condition 参数", "⚠️  Could not identify the condition parameter of CHECK_POINT. ")[l.n])

    except Exception as e:
        print(f"  (Could not introspect expression: {e})")
    
    # 删除帧引用，避免内存泄漏
    finally:
        if 'caller_frame' in locals():
            del caller_frame


    signal.checkpoint_fail(desc, compareInfo)

    # 如果需要截屏
    if failLogScreenWebDriver is not None:
        SELENIUM_LOG_SCREEN(failLogScreenWebDriver)

    # 记录下当前执行结果为失败
    # 注意：CHECK_POINT 可能在 suite_setup/suite_teardown 等“非用例上下文”被调用，
    # 此时 Runner.curRunningCase 为 None，只做信号通知，不写用例对象。
    if Runner.curRunningCase:
        Runner.curRunningCase.execRet = 'fail'
        Runner.curRunningCase.error = ('检查点不通过', 'checkpoint failed')[l.n]
        Runner.curRunningCase.stacktrace = "\n" * 3 + ('具体错误看测试步骤检查点', 'see checkpoint of case for details')[l.n]
    # 如果失败停止，中止此测试用例
    if failStop:
        raise CheckPointFail()


def LOG_IMG(imgPath: str, width: str = None):
    """
    add image in test report

    Parameters
    ----------
    imgPath: the path of image
    width:  display width of image in html, like 50% / 800px / 30em 
    """

    signal.log_img(imgPath, width)


def SELENIUM_LOG_SCREEN(driver, width: str = None):
    """
    add screenshot image of browser into test report when using Selenium
    在日志中加入selenium控制的 浏览器截屏图片

    Parameters
    ----------
    driver: selenium webdriver
    width:  display width of image in html, like 50% / 800px / 30em 
    """
    filename = datetime.now().strftime('%Y%m%d%H%M%S%f')
    filepath = f'log/imgs/{filename}.png'
    filepath_relative_to_log = f'imgs/{filename}.png'

    # 保存截图到指定路径
    driver.get_screenshot_as_file(filepath)
    signal.log_img(filepath_relative_to_log, width)