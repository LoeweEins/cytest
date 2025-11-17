# 用例框架执行引擎

import time, inspect # inspect 用于获取函数签名和参数
import os, types, importlib.util, fnmatch, traceback

from .signal import signal

from ..cfg import l

# 用例执行器，包括用例搜集和用例执行两个部分

# 检查点失败时 的异常类
# 定义时要继承 Exception
class CheckPointFail(Exception): 
    pass


# 依赖注入失败时 的异常类
# 参数没找到的话 抛出此异常
class DependencyInjectionFail(Exception): 
    pass


# 定义 依赖注入调用，从 GSTORE 中获取实参，再执行
def dependency_injection_call(func):
    from ..common import GSTORE
    
    sig = inspect.signature(func) # 返回函数签名对象，形参名和缺省值，存在 .parameters 属性中

    # params = [GSTORE[pname] for pname in sig.parameters.keys()]

    params = []
    for pname in sig.parameters.keys():
        if pname not in GSTORE:
            raise DependencyInjectionFail(
                (f'参数 `{pname}` 不在 GSTORE 中',
                 f'parameter `{pname}` not in GSTORE')[l.n]
            )
        
        params.append(GSTORE[pname])

    # 最后调用函数本身
    return func(*params)
    

# 标签匹配函数，有一个满足即返回 True
# 要用到 collector 收集的 tag
def tagmatch(pattern):
    for tag in Collector.current_case_tags:
        if fnmatch.fnmatch(tag,pattern):
            # print(' --> match')
            return True
    # print(' --> nomatch')
    return False


