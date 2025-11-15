from selenium import webdriver
class gs:
    driver : webdriver.Chrome
    # 类属性 gs.driver
    # 类型为 webdriver.Chrome
    # ：表示类型注解，指明 gs.driver 应该是 Chrome 浏览器的 WebDriver 实例




# 注意，lib目录下没有__init__.py文件，lib不是一个包
# 避免了命名冲突，加强了用户自定义
# 只能通过sys.path.append的方式导入