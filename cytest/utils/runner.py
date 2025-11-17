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



# 一个.py文件或者一个目录，都是一个suite
# 用例发现 + 执行计划生成
'''
搜集有效执行对象的 思路 伪代码如下：

循环遍历加载用例目录下面所有的 py 文件，导入为模块：
    从该模块找到测试相关的信息 比如：套件标签、套件初始化清除、用例类， 保存到字典meta中

    如果是用例模块，根据 选择条件 判断模块里面的用例 是否被选中，去掉没有选中的用例

从执行列表中去掉 没有包含用例的 目录模块
''' 
class Collector:
    
    # 在模块里，若有同名的列表变量，视为套件标签列表
    SUITE_TAGS = [
        'force_tags',
        'default_tags', # 暂时不用
    ]

    # 在模块里，若有同名函数，视为套件初始化清除函数
    SUITE_STS = [
        'suite_setup',
        'suite_teardown',
        'test_setup',
        'test_teardown',
    ]

    # 最终要执行的 相关模块文件
    # 既包括 .py 文件，也包括目录（__st__.py）
    exec_list = []

    # 最终要执行的 相关模块文件 和 对应的 对象
    # filepath  :  meta  字典
    exec_table = {}

    # 记录本次要执行的用例个数
    case_number = 0

    # 标签表，根据进入的路径，记录和当前模块相关的标签    
    #   格式如下  
    #     'force_tags': {
    #         'cases\\': ['冒烟测试', '订单功能'],
    #         'cases\\customer\\功能21.py': ['冒烟测试', '订单功能'],},
    #     'default_tags': {
    #         'cases\\customer\\功能31.py': ['优先级7']   }

    # 当前模块标签，格式为 路径 : [标签列表]
    suite_tag_table = {
        'force_tags':{},
        'default_tags':{}
    } 

    # 当前用例标签
    current_case_tags = []


    @classmethod
    def run(cls,
            casedir='cases',
            suitename_filters=[], # 套件通配过滤
            casename_filters=[],   # 用例通配过滤
            tag_include_expr=None,    
            tag_exclude_expr=None,   
            ):

        # 广播一个开始收集用例的 signal，支持中英德
        # 这里的info方法是 logger 的方法，被自动广播调用
        signal.info(
            ('\n\n===   [ 收集测试用例 ]  === \n',
            '\n\n===   [ collect test cases ]  === \n',
            '\n\n+++ [ Test sammeln ]  +++ \n')[l.n] # 中文，英文，德文
        )


        # os.walk 递归遍历目录树!!!
        # 只有 casedir 是类方法参数
        for (dirpath, dirnames, filenames) in os.walk(casedir):
            # 确保 __st__.py 在最前面
            # 根据 filenames 内容依次执行
            # 从根目录开始，先处理 __st__.py
            if '__st__.py' in filenames:
                filenames.remove('__st__.py')
                filenames.insert(0,'__st__.py')

            # 处理每个可能的执行模块文件
            for fn in filenames:
                filepath = os.path.join(dirpath, fn)
                if not filepath.endswith('.py'):
                    continue
                
                # 如果是 .py 文件，广播当前处理的模块文件路径
                signal.info(f'\n== {filepath} \n')

                # 动态导入模块
                module_name = fn[:-3]
                # 创建 spec 对象，按照文件路径和名称 动态创建
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                # 根据 spec 创建 module 对象
                module = importlib.util.module_from_spec(spec)
                # 执行这个文件，让 module 生效
                spec.loader.exec_module(module)


                # 处理一个模块文件
                cls.handleOneModule(module,filepath,
                    tag_include_expr,
                    tag_exclude_expr,
                    suitename_filters,
                    casename_filters)

        
        # *** 从执行列表中去掉 没有包含用例的 目录模块 ***
        # 先把 套件目录 和 套件文件 分别放到列表 sts, cases 中
        sts, cases = [], []
        for filepath in cls.exec_list:
            if filepath.endswith('py'):
                cases.append(filepath)
            else:
                # 是目录模块或者 __st__ 
                sts.append(filepath)

        # 再找出 套件目录中没有可以执行的测试文件的 哪些， 去掉不要
        # 对于目录路径，看有没有用例文件以它开头
        for stPath in sts:
            valid = False
            for  casePath in cases:
                if casePath.startswith(stPath):
                    valid = True
                    break
            if not valid:
                cls.exec_list.remove(stPath) 
                cls.exec_table.pop(stPath)


    # 处理一个模块文件
    @classmethod
    def handleOneModule(cls,module,filepath:str,
                        tag_include_expr:str,
                        tag_exclude_expr:str,
                        suitename_filters:list,
                        casename_filters:list):

        cur_module_name = os.path.basename(filepath).replace('.py','')

        stType = filepath.endswith('__st__.py')
        caseType = not stType

        if stType:
            filepath = filepath.replace('__st__.py','')

        # ======  搜寻该模块  hytest关键信息 ，保存在 meta 里面========
        meta = { 'type': 'casefile' if caseType else 'st' }
        if caseType: 
            meta['cases'] = []

        for name,item in module.__dict__.items():

            # __ 开头的名字肯定不是hytest关键名，跳过
            if name.startswith('__'):
                continue

            # 对应一个模块文件的，肯定是外部导入的模块，跳过
            if hasattr(item,'__file__'):
                continue

            # 外部模块内部导入的名字，跳过
            if hasattr(item,'__module__'):
                if item.__module__ != cur_module_name:
                    continue

            # signal.info(f'-- {name}')

            # 列表 ： 是 标签 吗？
            if isinstance(item, list):
                # 非标签关键字，跳过
                if name not in cls.SUITE_TAGS:
                    continue

                # 如果标签列表为空，跳过
                if not item:
                    continue

                meta[name] = item
                cls.suite_tag_table[name][filepath] = item

                signal.debug(f'-- {name}')

            # 函数 ： 是 初始化清除 吗？
            elif isinstance(item, types.FunctionType):
                # 非套件初始化清除关键字，跳过
                if name not in cls.SUITE_STS:
                    continue

                meta[name] = item

                signal.debug(f'-- {name}')
                    
            # 类  ： 是 用例 吗？
            elif caseType and isinstance(item, type):  
                # 没有 teststeps  ， 肯定不是用例类, 跳过
                if not hasattr(item, 'teststeps'):
                    signal.info(f'no teststeps in class "{name}", skip it.')
                    continue 
                
                # 如果 有 name    是 一个用例
                if  hasattr(item, 'name'):
                    # 同时有 ddt_cases ，格式不对
                    if hasattr(item, 'ddt_cases') : 
                        signal.info(f'both "name" and "ddt_cases" in class "{name}", skip it.')
                        continue 

                    meta['cases'].append(item())

                    signal.debug(f'-- {name}')

                # 如果 有 ddt_cases  是数据驱动用例，对应多个用例
                elif hasattr(item, 'ddt_cases') :  
                    for caseData in item.ddt_cases:
                        # 实例化每个用例，属性name，para设置好
                        case = item()
                        case.name, case.para = caseData['name'], caseData['para'],               
                        meta['cases'].append(case)  

                # 没有 name 也没有 ddt_cases， 类名作为用例名
                else:
                    item.name = name
                    meta['cases'].append(item())

                    signal.debug(f'-- {name}')


        # suite_tag_table 表中去掉 和 当前模块不相干的记录， 
        # 这样每次进入新的模块目录，就会自动去掉前面已经处理过的路径 标签记录
        new_suite_tag_table = {}
        for tname, table in cls.suite_tag_table.items(): 
            new_suite_tag_table[tname] = {p:v for p,v in table.items() if filepath.startswith(p)}                 
        cls.suite_tag_table = new_suite_tag_table
        
        
        #  用例模块 
        if caseType:            
            # 如果 没有用例 
            if not meta['cases']:
                signal.info(f'\n** no cases in this file, skip it.')
                return

            #  模块里面的用例 根据选择条件过滤 ，如果没有通过，会从 meta['cases'] 里面去掉
            cls.caseFilter(filepath, meta, tag_include_expr, tag_exclude_expr,suitename_filters,casename_filters)

            # 如果 用例都被过滤掉了
            if not meta['cases']:
                signal.info(f'\n** no cases in this file , skip it.')
                return

            # 待执行用例总数更新
            cls.case_number += len(meta['cases'])

        # __st__ 模块
        else:   
            #  应该包含 初始化 或者 清除 或者 标签 ，否则是无效模块，跳过
            if len(meta) == 1:
                signal.info(f'\n** no setup/teardown/tags in this file , skip it.')
                return 
            
        # 该模块文件 先暂时 加入执行列表
        cls.exec_list.append(filepath)
        cls.exec_table[filepath] = meta

    # 经过这个函数的执行， 最后 meta['cases'] 里面依然保存的，才是需要执行的用例
    @classmethod
    def caseFilter (cls,filepath:str, meta:dict,
                        tag_include_expr:str,
                        tag_exclude_expr:str,
                        suitename_filters:list,
                        casename_filters:list):
          
        # -------- 模块所有用例进行分析 ---------

        # 没有任何过滤条件，就不需要再看每个用例的情况了
        if not tag_include_expr and not tag_exclude_expr and not suitename_filters and not casename_filters:
            return 
        
        # 如果没有排除过滤， 
        # 并且 有 套件名过滤，并且整个套件被选中，就不需要再看每个用例的情况了
        # 一个用例文件 ，路径上的每一级都是一个套件
        if not tag_exclude_expr and suitename_filters:
            suitenames = filepath.split(os.path.sep) 
            # 套件文件名的后缀.py 去掉 作为套件名
            suitenames = [sn[:-3] if sn.endswith('.py') else sn  for sn in suitenames ]
            if cls._patternMatch(suitenames,suitename_filters):
                return
        
        # -------- 对每个用例进行分析 ---------

        passedCases = [] # 被选中的用例列表

        for caseClass in meta['cases']:     
            signal.debug(f'\n* {caseClass.name}')
            
            # ----------- 先看标签排除过滤 ------------
            
            # 得到当前模块相关的 套件 标签，就是表中现有的标签合并
            suite_tags = [t for tl in cls.suite_tag_table['force_tags'].values() for t in tl]
            # 用例本身的标签
            case_tags = getattr(caseClass, 'tags',[])
            # 用例关联的所有的标签
            cls.current_case_tags = set(suite_tags + case_tags)
            # print(cls.current_case_tags)

            # 如果有标签排除过滤
            if tag_exclude_expr:   
                # 条件满足，被排除
                if eval(tag_exclude_expr) == True: 
                    signal.debug(f'excluded for meeting expr : {tag_exclude_expr}')
                    continue 
                # 没有被排除
                else:
                    # 并且没有其他的 选择条件（只有标签排除过滤），就是被选中
                    if not casename_filters and not suitename_filters and not tag_include_expr:
                        passedCases.append(caseClass)
                        continue


            # --------- 再看 名字匹配过滤 ------------ 
            # 有用例名过滤
            if casename_filters:
                caseName = getattr(caseClass, 'name')
                #  通过用例名过滤 
                if  cls._patternMatch([caseName],casename_filters):
                    passedCases.append(caseClass)
                    continue


            # ----------- 再看标签匹配过滤 ------------
            if tag_include_expr :                
                if eval(tag_include_expr) == True:                    
                    passedCases.append(caseClass)
                    continue 

            # 上面一个选择条件也没有满足
            signal.debug(f'excluded for not meet any include rules')

        # 最终存放 通过过滤的用例
        meta['cases'] = passedCases


    @classmethod
    def _patternMatch (cls,names,patterns):
        for name in names:
            for pattern in patterns:
                if fnmatch.fnmatch(name,pattern):
                    return True
        return False