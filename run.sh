#!/bin/bash

python3 -m cytest "$@"
# 通过 cytest.run 模块运行 cytest 主程序
# "$@" 传递所有命令行参数
# 入口是__main__.py 文件