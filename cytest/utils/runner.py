# checked
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



    # 用os.walk递归遍历casedir下所有.py文件
    # 动态import每个.py文件为模块
    # 对每个模块调用 handleOneModule 进行处理
    # 删除无用的套件
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


    # 一个模块如何被拆解成 meta 信息
    # 判断文件是 __st__ 还是 用例模块
    # 遍历模块内所有属性和对象，找出标签列表、初始化清除函数、用例类
    # 维护标签表 suite_tag_table
    # 用例过滤的流程：调用 caseFilter 方法，统计case_number
    # st文件： 只处理 标签、初始化清除
    @classmethod
    def handleOneModule(cls,module,filepath:str,
                        tag_include_expr:str,
                        tag_exclude_expr:str,
                        suitename_filters:list,
                        casename_filters:list):

        # 去掉 .py 后缀
        cur_module_name = os.path.basename(filepath).replace('.py','')

        # 确认当前模块是 __st__ 还是 用例模块
        stType = filepath.endswith('__st__.py')
        caseType = not stType

        if stType:
            filepath = filepath.replace('__st__.py','')

        # ======  搜寻该模块  cytest关键信息 ，保存在 meta 里面========

        # 初始化 meta 字典
        meta = { 'type': 'casefile' if caseType else 'st' }
        # 如果该模块是用例模块，额外初始化 cases 列表存入 meta
        if caseType: 
            meta['cases'] = []

        # 遍历模块内 所有属性和对象（属性所指的对象）
        for name,item in module.__dict__.items():
            # __ 开头的名字肯定不是cytest关键名，跳过
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

            # 列表 ： 是 标签 吗？（也可以是 __st__ 内的标签）
            if isinstance(item, list):
                # 非标签关键字，跳过
                if name not in cls.SUITE_TAGS:
                    continue

                # 如果标签列表为空，跳过
                if not item:
                    continue
                # 记录到 标签表 中
                meta[name] = item
                # 记录到 路径标签表 
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
                
                # 如果 有 name  是 一个用例
                if  hasattr(item, 'name'):
                    # 同时有 ddt_cases ，格式不对
                    if hasattr(item, 'ddt_cases') : 
                        signal.info(f'both "name" and "ddt_cases" in class "{name}", skip it.')
                        continue 
                    
                    # 实例化用例类，加入用例列表
                    meta['cases'].append(item()) # !!! 因为每个用例是一个类，要实例化

                    signal.debug(f'-- {name}')

                # 没有 name，有 ddt_cases，实例化每一个用例
                elif hasattr(item, 'ddt_cases') :  
                    for caseData in item.ddt_cases:
                        # 实例化每个用例，属性name，para设置好
                        case = item()
                        case.name, case.para = caseData['name'], caseData['para'],               
                        meta['cases'].append(case)  
                        # meta中'cases'既保存名字，也保存参数

                # 没有 name 也没有 ddt_cases， 类名作为用例名
                else:
                    item.name = name
                    meta['cases'].append(item())

                    signal.debug(f'-- {name}')


        # suite_tag_table 表中去掉 和 当前模块不相干的记录， 
        # 这样每次进入新的模块目录，就会自动去掉前面已经处理过的路径 标签记录
        # 设置当前 suite 的标签
        # 这里是一个小 trick
        new_suite_tag_table = {}
        for tname, table in cls.suite_tag_table.items(): 
            new_suite_tag_table[tname] = {p:v for p,v in table.items() if filepath.startswith(p)}                 
        cls.suite_tag_table = new_suite_tag_table
        
        
        #  用例过滤
        if caseType:            
            # 如果 没有用例 skip 掉
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
            if len(meta) == 1: # 只有一个初始的 'type' : 'st'
                signal.info(f'\n** no setup/teardown/tags in this file , skip it.')
                return 
            
        # 该模块文件 先暂时 加入执行列表
        cls.exec_list.append(filepath)
        cls.exec_table[filepath] = meta

    # 经过这个函数的执行， 最后 meta['cases'] 里面依然保存的，才是需要执行的用例
    # 先看tag_exclude_expr，满足则排除
    # 再看 casename_filters，满足则加入
    # 再看 tag_include_expr，满足则加入
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
        
        # 如果没有排除过滤
        # 并且 有 套件名过滤，并且整个套件被选中，就不需要再看每个用例的情况了
        # 一个用例文件 ，路径上的每一级都是一个套件
        if not tag_exclude_expr and suitename_filters:
            suitenames = filepath.split(os.path.sep) # os.path.sep 跨平台的路径分隔符
            # 套件文件名的后缀.py 去掉 作为套件名
            suitenames = [sn[:-3] if sn.endswith('.py') else sn  for sn in suitenames ]
            if cls._patternMatch(suitenames,suitename_filters):
                return
        # cases/order/test_login.py
        # .split(os.path.sep) 拆成：['cases', 'order', 'test_login.py']


        # -------- 对每个用例进行分析 ---------

        passedCases = [] # 被选中的用例列表

        for caseClass in meta['cases']:     
            signal.debug(f'\n* {caseClass.name}')
            
            # ----------- 先看标签排除过滤 ------------
            # 这里有点没看懂!!!有点像小 trick，再问问看
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
                # eval()表示执行字符串表达式
                
                if eval(tag_exclude_expr) == True: 
                    signal.debug(f'excluded for meeting expr : {tag_exclude_expr}')
                    continue 
                # 没有被排除
                else:
                    # 并且没有其他的 选择条件（只有标签排除过滤），就是被选中
                    if not casename_filters and not suitename_filters and not tag_include_expr:
                        passedCases.append(caseClass)
                        continue


            # --------- 再看 名字匹配加入 ------------ 
            # 有用例名加入
            if casename_filters:
                caseName = getattr(caseClass, 'name')
                #  通过用例名过滤 
                if  cls._patternMatch([caseName],casename_filters):
                    passedCases.append(caseClass)
                    continue


            # ----------- 再看标签匹配加入 ------------
            if tag_include_expr :                
                if eval(tag_include_expr) == True:                    
                    passedCases.append(caseClass)
                    continue 

            # 上面一个选择条件也没有满足
            signal.debug(f'excluded for not meet any include rules')

        # 最终存放 通过过滤的用例
        meta['cases'] = passedCases


    # 用例名/套件名匹配
    @classmethod
    def _patternMatch (cls,names,patterns):
        for name in names:
            for pattern in patterns:
                if fnmatch.fnmatch(name,pattern):
                    return True
        return False
    

    '''
执行自动化的 思路 伪代码如下：

Runner负责：
按什么顺序跑？什么时候跑哪个 suite_setup / suite_teardown？
某个套件初始化失败后，下游都不要跑了。
每个 case 的 setup / steps / teardown 怎么调？
异常怎么处理？日志和报告怎么通知？

1. 先保证 exec_list 中 该teardown的地方插入 teardown


执行前， exec_list 示例如下 目录
[
    'cases\\',
    'cases\\.功能3.py',
    'cases\\功能1.py',
    'cases\\功能2.py',
    'cases\\customer\\',
    'cases\\customer\\功能21.py',
    'cases\\order\\',
    'cases\\order\\功能31.py',
] 

list只有路径，但是table有路径和meta信息

遍历 exec_table 中的每个对象：  {filepath : meta} 
    如果 该执行对象 type 是 st， 说明是 套件目录：
        如果有 tear_down, 到 exec_list 中 找到合适的位置，插入 tear_down 操作

执行完此步骤后， exec_list 示例如下
[
    'cases\\',
    'cases\\.功能3.py',
    'cases\\功能1.py',
    'cases\\功能2.py',
    'cases\\customer\\',
    'cases\\customer\\功能21.py',
    'cases\\customer\\--teardown--',
    'cases\\order\\',
    'cases\\order\\功能31.py',
    'cases\\order\\--teardown--',
    'cases\\--teardown--'
] 
    

2. 然后执行测试

suite_setup_failed_list = [] 记录初始化失败的套件

for name in  exec_list：    
    检查 这个name 是否以 suite_setup_failed_list 里面的内容开头
    如果是 continue

    if name 以 --teardown--  结尾：
        去掉 --teardown-- 部分，找到 exec_table中的对象执行 teardown
    else：
        以name 为key， 找到 exec_table中的对象：
            if 类型是 st ：
                如果 有 suite_setup:
                    执行 suite_setup
                    如果 suite_setup 抛异常：
                        添加 name 到 suite_setup_failed_list 
            elif 类型是 case：
                执行 case里面的用例：
                    先执行用例的 setup
                    如果 setup 异常，后面的 teststeps 和 teardown都不执行


''' 
class Runner:
    
    curRunningCase = None 

    # 记录所有测试用例的执行结果，每个元素都是用户定义的测试用例类实例
    #  执行过程中写入了测试几个到每个测试用例类中
    case_list = []


    # 0）没有用例就返回 2
    # 1）为 exec_list 中的每个 st 插入 teardown
    # 2）发送test_start 信号
    # 3）执行测试树 execTest()
    # 4）发送 test_end 信号
    # 5）从 GSTORE 中获取最终结果返回
    @classmethod
    def run(cls,):
        
        signal.info(
            ('\n\n===   [ 执行测试用例 ]  === \n',
            '\n\n===   [ execute test cases ]  === \n')[l.n]
        )

        # 如果本次没有可以执行的用例（可能是过滤项原因），直接返回
        if not Collector.exec_list:
            signal.error(('!! 没有可以执行的测试用例','!! No cases to run')[l.n])
            return 2 # 2 表示没有可以执行的用例

        signal.info(f"{('预备执行用例数量','Number of cases to run')[l.n]} : {Collector.case_number}\n")

        # 执行用例时，为每个用例分配一个id，方便测试报告里面根据id跳转到用例
        cls.caseId = 0


        # 1. 先保证 exec_list 中 该teardown的地方插入 teardown记录
        # 回头再看一下 ._insertTeardownToExecList()方法
        for name,meta in Collector.exec_table.items():
            if meta['type'] == 'st' and 'suite_teardown' in meta:
                cls._insertTeardownToExecList(name)
        

        # print(Collector.exec_list)

        # 2. 然后执行自动化流程         
        signal.test_start()
        cls.execTest() ########################## 紧接着在后面定义了 #############################
        signal.test_end(cls)

        from cytest.common import  GSTORE
        # 0 表示执行成功 , 1 表示有错误 ， 2 表示没有可以执行的用例, 3 缺省值 表示未知错误
        return GSTORE.get('---ret---',3)

    @classmethod
    def execTest(cls):

        suite_setup_failed_list = [] # 记录初始化失败的套件


        #--------------------- 遍历 exec_list 中的每个元素 -----------------------
        for name in  Collector.exec_list:

            # 检查 这个name 是否属于套件初始化失败影响的范围
            affected = False
            for suite_setup_failed in suite_setup_failed_list:
                if name.startswith(suite_setup_failed):
                    affected = True
                    break
            if affected:
                continue


            # 套件目录清除
            if name.endswith('--teardown--'):
                # 去掉 --teardown-- 部分
                name = name.replace('--teardown--','')
                # 找到 exec_table 中的对象执行 teardown
                suite_teardown = Collector.exec_table[name]['suite_teardown']
                                
                signal.teardown_begin(name,'suite_dir')
                begin_time = time.time()  # 记录开始时间
                
                try:
                    # suite_teardown()
                    dependency_injection_call(suite_teardown) # 放函数名或者方法名，自动调用
                except Exception as e:
                    # 套件目录 清除失败
                    signal.teardown_fail(name,'suite_dir', e, cls.trim_stack_trace(traceback.format_exc()))
                    
                end_time = time.time()
                duration = end_time - begin_time                            
                signal.teardown_end(name, 'suite_dir', duration)


            else:
                meta = Collector.exec_table[name]

                # 进入套件目录
                if meta['type'] == 'st': 

                    signal.enter_suite(name,'dir')

                    suite_setup = meta.get('suite_setup')
                    
                    # 套件目录初始化
                    if suite_setup:                     
                        signal.setup_begin(name,'suite_dir')
                        begin_time = time.time()   
                        try:                            
                            # suite_setup()  
                            dependency_injection_call(suite_setup)
                        except Exception as e:
                            # 套件目录 初始化失败,
                            signal.setup_fail(name,'suite_dir', e, cls.trim_stack_trace(traceback.format_exc()))
                            # 记录到 初始化失败目录列表 中， 该套件目录内容都不会再执行
                            suite_setup_failed_list.append(name)

                        end_time = time.time()
                        duration = end_time - begin_time 
                        signal.setup_end(name, 'suite_dir', duration)

                # 进入用例文件
                elif meta['type'] == 'casefile': 

                    signal.enter_suite(name,'file')
                    
                    # 用例文件 初始化
                    suite_setup = meta.get('suite_setup')
                    if suite_setup:                           
                        signal.setup_begin(name,'suite_file') 
                        begin_time = time.time()    
                        try:                            
                            # suite_setup()
                            dependency_injection_call(suite_setup)
                        except Exception as e:
                            # 套件文件 初始化失败 
                            signal.setup_fail(name,'suite_file', e, cls.trim_stack_trace(traceback.format_exc()))
                            end_time = time.time()
                            duration = end_time - begin_time                            
                            signal.setup_end(name, 'suite_file', duration)
                            # 该套件文件内容都不会再执行
                            continue 
                        
                        end_time = time.time()
                        duration = end_time - begin_time                            
                        signal.setup_end(name, 'suite_file', duration)

                    # 执行套件文件里面的用例
                    cls._exec_cases(meta)
                    
                    # 用例文件 清除
                    suite_teardown = meta.get('suite_teardown')
                    if suite_teardown:
                        signal.teardown_begin(name,'suite_file')   
                        begin_time = time.time()                       
                        try:
                            # suite_teardown()
                            dependency_injection_call(suite_teardown)
                        except Exception as e:
                            # 套件文件 清除失败
                            signal.teardown_fail(name, 'suite_file', e, cls.trim_stack_trace(traceback.format_exc()))
                            
                        end_time = time.time()
                        duration = end_time - begin_time                            
                        signal.teardown_end(name, 'suite_file', duration)


    #  exec_list 中 找到 stName 对应的 teardown的地方插入 teardown记录
    @classmethod
    def _insertTeardownToExecList(cls,stName):
        findStart = False
        insertPos = -1
        for pos, name in enumerate(Collector.exec_list):
            # 这样肯定会先找到 等于 stName 的位置
            if not findStart:
                if name != stName:
                    continue
                else:
                    findStart = True
            else:
                # print(name,stName)
                # 接下来找 不以 stName 开头的那个元素，就在此位置插入
                if not name.startswith(stName):
                    insertPos = pos
                    break
        
        # 直到最后也没有找到，是用例根目录，添加到最后
        tearDownName = stName+'--teardown--'

        if insertPos == -1:
            Collector.exec_list.append(tearDownName)
        else:            
            Collector.exec_list.insert(insertPos,tearDownName)
            

    # 执行套件文件里面的多个用例
    @classmethod
    def _exec_cases(cls,meta):
        # 缺省  test_setup test_teardown
        test_setup = meta.get('test_setup')
        test_teardown = meta.get('test_teardown')


        #------------------ 取出每一个用例，记录一些需要写在日志里的信息 -----------------------
        for case in meta['cases']:
            # 记录到 cls.case_list 中，方便测试结束后，遍历每个测试用例
            cls.case_list.append(case)

            case_className = type(case).__name__

            # 用例 id 自动递增 分配， 这个id 主要是 作为 产生的HTML日志里面的html元素id
            cls.caseId += 1  

            case._case_begin_time = time.time()
            signal.enter_case(cls.caseId, case.name, case_className)
            
            # 记录当前执行的case
            cls.curRunningCase = case
            
            #---------------- 如果用例有 setup，就执行 setup -----------------
            caseSetup = getattr(case,'setup',None)

            setupFunc = None
            if caseSetup:
                setupFunc = caseSetup
                setupType = 'case'
            elif test_setup: # 如果用例没有 setup ，但是有缺省  test_setup
                setupFunc = test_setup
                setupType = 'case_default'

            if setupFunc:
                case._cytest_case_setup_begin_time = time.time()
                signal.setup_begin(case.name, setupType)
                
                try:
                    # setupFunc()
                    dependency_injection_call(setupFunc)
                    
                    case._cytest_case_setup_end_time = time.time()
                    case._setup_duration = case._cytest_case_setup_end_time - case._cytest_case_setup_begin_time
                    signal.setup_end(case.name, setupType, case._setup_duration)
                except Exception as e:
                    signal.setup_fail(case.name, setupType, e, cls.trim_stack_trace(traceback.format_exc()))
                    continue # 初始化失败，这个用例的后续也不用执行了                

            signal.case_steps(case.name)


            #------------------------------- 执行用例 -------------------------------
            try:
                # 先预设结果为通过，如果有检查点不通过，那里会设置为fail
                case.execRet = 'pass'
                
                case._cytest_case_steps_begin_time = time.time()
               
                dependency_injection_call(case.teststeps)
            
            except CheckPointFail as e:   
                case.execRet = 'fail'
                case.error = e 
                case.stacktrace = cls.trim_stack_trace(traceback.format_exc())
                   
            except Exception as e:  
                case.execRet = 'abort'
                case.error = e
                case.stacktrace = cls.trim_stack_trace(traceback.format_exc())


            # 用例结果 通知 各日志模块            
            case._cytest_case_steps_end_time = time.time()
            case._steps_duration = case._cytest_case_steps_end_time - case._cytest_case_steps_begin_time
            
            signal.case_result(case)  
                


            #--------------------------------- 用例 teardown -----------------------------       
            caseTeardown = getattr(case,'teardown',None)

            teardownFunc = None
            if caseTeardown:
                teardownFunc = caseTeardown
                teardownType = 'case'
            elif test_teardown: # 如果用例没有 teardown ，但是有缺省  test_teardown
                teardownFunc = test_teardown
                teardownType = 'case_default'
                
            if teardownFunc:
                case._cytest_case_teardown_begin_time = time.time()
                signal.teardown_begin(case.name, teardownType)
                try:
                    # teardownFunc()   
                    dependency_injection_call(teardownFunc)
                    case._cytest_case_teardown_end_time = time.time()
                    case._teardown_duration = case._cytest_case_teardown_end_time - case._cytest_case_teardown_begin_time
                    signal.teardown_end(case.name, teardownType, case._teardown_duration)
                except Exception as e:
                    signal.teardown_fail(case.name, teardownType, e, cls.trim_stack_trace(traceback.format_exc()))
           
           
            # 离开用例
            case._case_end_time = time.time()
            case._case_duration = case._case_end_time - case._case_begin_time
            signal.leave_case(cls.caseId, duration=case._case_duration)

    @classmethod
    def trim_stack_trace(cls, stacktrace):

        # 依赖注入失败, 删除调用堆栈前面一大段信息
        if 'cytest.utils.runner.DependencyInjectionFail:' in stacktrace:  
            stacktrace = stacktrace.split("cytest.utils.runner.DependencyInjectionFail:",1)[-1].strip()
            return stacktrace
        

        if 'in dependency_injection_call' in  stacktrace:
            stacktrace = stacktrace.split("in dependency_injection_call",1)[-1].split("\n",2)[-1].strip()
        
        if stacktrace.startswith('~~~~~'):
                stacktrace = stacktrace.split("\n",1)[1].strip() 
        
        # 如果 Traceback 后3行信息固定的是 common.py 里面的 CheckPointFail ，也多余， 不要
        if ', in CHECK_POINT' in  stacktrace:
            stacktrace = stacktrace.rsplit("\n",4)[0].strip()

        return stacktrace
        # 干净的栈信息，用于日志显示


if __name__ == '__main__':
    Collector.run(
        # suitename_filters=['cust*'],
        # casename_filters=['cust*','or*'],
        # tag_include_expr="(tagmatch('优先级4')) or (tagmatch('UITest'))  or  (tagmatch('Web*'))"
        )

    # print(Collector.exec_table)

    Runner.run()

