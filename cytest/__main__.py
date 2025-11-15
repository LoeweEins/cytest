from .run import *

exit(run())

# run() 返回 0，成功；返回1，失败
# 执行包时必须先「加载包」
# 加载包时自动执行 __init__.py
# 加载完成后，执行 __main__.py