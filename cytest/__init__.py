from .common import signal,GSTORE,INFO,STEP,CHECK_POINT,LOG_IMG,SELENIUM_LOG_SCREEN, CheckPointFail
# api 暴露在 cytest 包顶层，方便直接导入

import os, sys
sys.path.append(os.getcwd()) # 添加当前工作目录到sys.path
# 把项目根目录加入 sys.path，让 lib/ 能被 import
# os.getcwd() 获取当前工作目录