from cytest import STEP, INFO, CHECK_POINT


class cSANDBOX0001:
    name = "SANDBOX-0001-示例用例（用于临时验证框架能力）"
    tags = ["now"]

    def teststeps(self):
        STEP(1, "输出一条 INFO，验证 Vue 报告记录")
        INFO("hello sandbox")
        STEP(2, "一个最简单检查点")
        CHECK_POINT("1 + 1 == 2", 1 + 1 == 2)

