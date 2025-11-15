#!/bin/bash

# 删除旧构建目录
rm -rf dist # 删除旧的分发文件
rm -rf build # 删除旧的构建文件
rm -rf cytest.egg-info # 删除旧的元数据目录

# 构建 wheel 包
python3 -m build --wheel

# 上传到 TestPyPI
twine upload dist/* --repository testpypi