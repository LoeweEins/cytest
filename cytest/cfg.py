# checked
# 这个文档用于定语言和报告标题、URL前缀
supportedLang = ['zh','en','de']

# l类 用于保存语言编号
# l.n 和 l.LANGS都需要动态映射，所以用类来实现
class l:
    LANGS = {
        'zh' : 0,
        'en' : 1,
        'de' : 2,
    }
    n = None  # 当前使用的语言编号

# 解析命令行参数，设置语言
import sys
if '--lang' in sys.argv:
    try:
        idx = sys.argv.index('--lang') # 找到 --lang 参数位置
        lang = sys.argv[idx+1] #找到语言参数值
        if lang in supportedLang:
            l.n = l.LANGS[lang] # 设置语言编号 0 或 1
    except:...

if l.n is None: # 未通过命令行传参
    import locale
    if 'zh_CN' in locale.getdefaultlocale():
        l.n = l.LANGS['zh']
    elif 'de_DE' in locale.getdefaultlocale():
        l.n = l.LANGS['de']
    else :
        l.n = l.LANGS['en']


LANG_TABLE = {
    '测试报告' : [
        '测试报告',
        'Test Report',
        'Testbericht',
    ],
    '指定测试报告标题' : [
        '指定测试报告标题',
        'set test report title',
        'Testbericht-Titel festlegen',
    ],
}


# 返回当前使用语言字符串
def ls(lookupStr):
    return LANG_TABLE[lookupStr][l.n]

class Settings:
    auto_open_report = True
    report_title = '' # 命令行参数会设置,并且有缺省值
    report_url_prefix = '' # 命令行参数会设置,并且有缺省值
    use_vue_report = False