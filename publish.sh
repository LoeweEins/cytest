#!/bin/bash

# 删除旧构建目录
rm -rf dist # 删除旧的分发文件
rm -rf build # 删除旧的构建文件
rm -rf cytest.egg-info # 删除旧的元数据目录

# 构建 wheel 包（正式发布用）
python3 -m build --wheel

# 3. 上传到 PyPI，不是 testpypi
twine upload dist/*.whl # 只上传 wheel，不上传 tar.gz

# 4. 保持终端窗口不立即退出（可选）
read -n 1 -s -r -p "Press any key to continue..."
echo