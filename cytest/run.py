import re,os,traceback
from .cfg import l, Settings
# 模块在被引用时，就会被执行，进行初始化，解析命令行参数得到解析
# from 的引用是创建模块变量的副本，而不是引用模块变量本身
# import 则是引用模块变量本身
import argparse
from .product import version


def tagExpressionGen(argstr):
    tagRules = []
    for part in argstr:
        # 有单引号，是表达式
        if "'" in part:
            rule = re.sub(r"'.+?'", lambda m :f'tagmatch({m.group(0)})' , part)
            tagRules.append(f'({rule})')
        # 是简单标签名
        else:
            rule = f"tagmatch('{part}')"
            tagRules.append(f'{rule}')
    return ' or '.join(tagRules)

def run() :
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', action='version', version=f'cytest v{version}',
                        help=("显示版本号", 'display cytest version')[l.n])
    parser.add_argument('--lang', choices=['zh', 'en', 'de'],
                        help=("设置工具语言", 'set language')[l.n])
    parser.add_argument('--new', metavar='project_dir',
                        help=("创建新项目目录", "create a project folder")[l.n])
    parser.add_argument("case_dir", nargs='?', default='cases',
                        help=("用例根目录", "")[l.n])
    parser.add_argument("--loglevel", metavar='level_number', type=int, default=3,
                        help=("日志级别 0,1,2,3,4,5(数字越大，日志越详细)", "log level 0,1,2,3,4,5(bigger for more info)")[l.n])

    parser.add_argument('--auto_open_report', choices=['yes', 'no'], default='yes',
                        help=("测试结束不自动打开报告", "don't open report automatically after testing")[l.n])
    parser.add_argument("--report_title", metavar='report_title',
                        default=['测试报告','Test Report'][l.n],
                        help=['指定测试报告标题','set test report title'][l.n])
    parser.add_argument("--report_url_prefix", metavar='url_prefix',
                        default='',
                        help=['测试报告URL前缀','test report URL prefix'][l.n])

    parser.add_argument("--test", metavar='case_name', action='append', default=[],
                        help=("用例名过滤，支持通配符", "filter by case name")[l.n])
    parser.add_argument("--suite", metavar='suite_name', action='append', default=[],
                        help=("套件名过滤，支持通配符", "filter by suite name")[l.n])
    parser.add_argument("--tag", metavar='tag_expression', action='append', default=[],
                        help=("标签名过滤，支持通配符", "filter by tag name")[l.n])
    parser.add_argument("--tagnot", metavar='tag_expression', action='append', default=[],
                        help=("标签名反向过滤，支持通配符", "reverse filter by tag name")[l.n])
    parser.add_argument("-A", "--argfile", metavar='argument_file',
                        type=argparse.FileType('r', encoding='utf8'),
                        help=("使用参数文件", "use argument file")[l.n])
    parser.add_argument("-saic", "--set-ai-context", metavar='ai_context_file',
                        type=str,
                        help=("设置 AI Context 文件（比如 GEMINI.md）内容，加入cytest使用方法", "set AI context file(like GEMINI.md) by appending cytest guide")[l.n])

    args = parser.parse_args()

    # 有参数放在文件中，必须首先处理
    if args.argfile:
        fileArgs = [para for para in args.argfile.read().replace('\n',' ').split() if para]
        print(fileArgs)
        args = parser.parse_args(fileArgs,args)

    # 设置AI上下文内容
    if args.set_ai_context:
        ctxFile = args.set_ai_context
        ctxContent = ''
        
        if os.path.exists(ctxFile):
            with open(ctxFile, encoding='utf8') as f:
                ctxContent = f.read() + '\n\n'
               
            if '# cytest 自动化测试框架 简介' in ctxContent:   
                print(f'{ctxFile} {("里面已经包含了cytest资料", "already includes cytest guide.")[l.n]}')
                exit()

        cytestGuideFile = os.path.join(os.path.dirname(__file__), 'utils','cytest.md')   
        ctxContent += open(cytestGuideFile, encoding='utf8').read()

        with open(ctxFile, 'w', encoding='utf8') as f:
            f.write(ctxContent)

        print(f'{ctxFile} {("里面增加了cytest资料", "now includes cytest guide.")[l.n]}')
        exit()
        

    # 看命令行中是否设置了语言
    if args.lang:
        l.n = l.LANGS[args.lang]

    # 报告标题
    Settings.report_title = args.report_title

    # 测试结束后，是否自动打开测试报告
    Settings.auto_open_report = True if args.auto_open_report=='yes' else False

    # 测试结束后，要显示的测试报告的url前缀,比如： run.bat --report_url_prefix http://127.0.0.1
    # 可以本机启动http服务，比如：python -m http.server 80 --directory log
    # 方便 jenkins上查看
    Settings.report_url_prefix = args.report_url_prefix

    # 创建项目目录
    if args.new:
        projDir =  args.new
        if os.path.exists(projDir):
            print(f'{projDir} already exists！')
            exit(2)
        os.makedirs(f'{projDir}/cases')
        with open(f'{projDir}/cases/case1.py','w',encoding='utf8') as f:
            caseContent = [
'''class c1:
    name = '用例名称 - 0001'

    # 测试用例步骤
    def teststeps(self):
        ret = 1
        ''' ,

'''class c1:
    name = 'test case name - 0001'

    # test case steps
    def teststeps(self):...''',
    ][l.n]
            f.write(caseContent)

        exit()


    if not os.path.exists(args.case_dir) :
        print(f' {args.case_dir} {("目录不存在，工作目录为：","folder not exists, workding dir is:")[l.n]} {os.getcwd()}')
        exit(2)  #  '2' stands for no test cases to run

    if not os.path.isdir(args.case_dir) :
        print(f' {args.case_dir}  {("不是目录，工作目录为：","is not a folder, workding dir is:")[l.n]} {os.getcwd()}')
        exit(2)  #  '2' stands for no test cases to run

    # 同时执行log里面的初始化日志模块，注册signal的代码
    from .utils.log import LogLevel
    from .utils.runner import Collector, Runner

    LogLevel.level = args.loglevel
    # print('loglevel',LogLevel.level)


    # --tag "'冒烟测试' and 'UITest' or (not '快速' and 'fast')" --tag 白月 --tag 黑羽

    tag_include_expr = tagExpressionGen(args.tag)
    tag_exclude_expr = tagExpressionGen(args.tagnot)

    # print(tag_include_expr)
    # print(tag_exclude_expr)


    print(f'''           
    *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *     
    *       cytest {version}            www.byhy.net       *
    *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *
    '''
    )

    os.makedirs('log/imgs', exist_ok=True)

    try:
        Collector.run(
            casedir=args.case_dir,
            suitename_filters=args.suite,
            casename_filters=args.test,
            tag_include_expr=tag_include_expr,
            tag_exclude_expr=tag_exclude_expr,
            )
    except:
        print(traceback.format_exc())
        print(('\n\n!! 搜集用例时发现代码错误，异常终止 !!\n\n', 
               '\n\n!! Collect Test Cases Exception Aborted !!\n\n')[l.n])
        exit(3)


    
    # 0 表示执行成功 , 1 表示有错误 ， 2 表示没有可以执行的用例
    result =  Runner.run()

    # keep 10 report files at most
    ReportFileNumber = 10
    import glob
    reportFiles = glob.glob('./log/report_*.html')
    fileNum = len(reportFiles)
    if fileNum >= ReportFileNumber:
        reportFiles.sort()
        for rf in reportFiles[:fileNum-ReportFileNumber]:
            try:
                os.remove(rf)
            except:...

    return result


if __name__ == '__main__':
    exit(run())