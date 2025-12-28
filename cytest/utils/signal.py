# checked
# 信号广播，不同组件间传递消息
# 在 runner 中引用了
# 迷你事件系统 signal-slot，多个组件订阅同一个事件，事件触发，同时通知所有订阅者
class Signal:
    _clients = [] # 监听器列表
    _curMethodName = None # 要广播的事件名
    # signal.register(consoleLogger) # 注册监听器

    def register(self, client): # 支持 单客户端/多客户端 注册
        if isinstance(client,list):
            self._clients += client # 列表合并
        else:
            self._clients.append(client) # 添加单个客户端

    def _broadcast(self,*arg,**kargs): # 位置参数装进 tuple，关键字参数装进 dict

        for logger in self._clients:
            method = getattr(logger,self._curMethodName,None)
            if method:
                method(*arg,**kargs)

    # 兜底方法 __getattr__()
    # 动态获取方法名，返回广播函数
    # 体现了 Python 的动态特性
    def __getattr__(self, attr): # 调用方法时，先获取方法名
        self._curMethodName = attr # 动态获取方法名，字符串
        return self._broadcast # 获取方法名后，返回广播函数

signal = Signal()
