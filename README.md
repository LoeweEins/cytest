# Introduction ｜ 工具介绍
This is a automation test framework written by Zeen for the first time, where I merged the mature and mainly used framework 'pytest' and an experimental framework 'hytest'. The two automation frameworks almost built my entire carrier as a software testing engineer.

`cytest` is named from the spelling of my name `ze` in `Wade-Giles Romanization System`, that is `chak`. I appreciate this character so much that I named it as a part of my first project which means a lot to me.

`cytest` might not be comparable to other test frameworks on Github, but I'm working hard on it and constantly update my little `cytest`.

I'm also applying `fixture` mechanism to `cytest` to make sure it is so popular and evolves with the latest trend.

## Installation ｜ 安装

### From GitHub ｜ 从 GitHub

```sh
git clone https://github.com/LoeweEins/cytest.git
cd cytest
pip install -e .
```


### From PyPI (not available yet) ｜ 从 PyPI

```sh
pip install cytest
```

### Requirements ｜ 要求

- Python >= 3.9

## Run ｜ 运行

### Quick start ｜ 快速运行

```sh
cd cytest          # enter the directory where the 'cases' folder is
python3 -m cytest   
```

### Options ｜ 命令行参数

```sh
# language zh / en / de
python3 -m cytest --lang en

# directory
python3 -m cytest cases/order
python3 -m cytest cases/web_auto

# suite name
python3 -m cytest --suite customer --suite order

# case name
python3 -m cytest --test "*API-0001*"

# tag
python3 -m cytest --tag 接口测试

# auto open report
python3 -m cytest --auto_open_report yes

# report title
python3 -m cytest --report_title "Sprint 12 Regression"

# log level
python3 -m cytest --loglevel 4
```

### Output ｜ 输出

Reports are generated under the `log/` directory.