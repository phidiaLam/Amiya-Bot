import re

from typing import *
from core.builtin.message import Message, MessageMatch, Event, Verify, equal
from core.builtin.timedTask import TasksControl
from core.builtin.messageChain import Chain

CORO = Coroutine[Any, Any, Optional[Chain]]
PREFIX = Union[bool, List[str]]
KEYWORDS = Union[str, equal, re.Pattern, List[Union[str, equal, re.Pattern]]]
FUNC_CORO = Callable[[Message], CORO]
EVENT_CORO = Callable[[Event], CORO]
VERIFY_CORO = Callable[[Message], Coroutine[Any, Any, Union[bool, Tuple[bool, int], Tuple[bool, int, List[str]]]]]
MIDDLE_WARE = Callable[[Message], Coroutine[Any, Any, Optional[Message]]]


class Handler:
    def __init__(self,
                 function_id: str,
                 function: FUNC_CORO,
                 keywords: KEYWORDS = None,
                 custom_verify: VERIFY_CORO = None,
                 check_prefix: PREFIX = True):
        """
        处理器对象
        将注册到功能候选列表的功能处理器，提供给消息处理器（message_handler）筛选出功能轮候列表。
        不必主动实例化本类，请使用注册器注册功能函数。
        示例：
        @bot.on_group_message(function_id='hello', keywords='你好')
        async def my_function(data: Message):
            ...

        :param function_id:   功能ID
        :param function:      功能函数
        :param keywords:      内置校验方法的关键字，支持字符串、正则、全等句（equal）或由它们构成的列表
        :param custom_verify: 自定义校验方法
        :param check_prefix:  是否校验前缀或指定需要校验的前缀
        """
        self.function_id = function_id
        self.function = function
        self.keywords = keywords
        self.custom_verify = custom_verify
        self.check_prefix = check_prefix

    def __repr__(self):
        return f'<Handler, {self.function_id}, {self.keywords}>'

    def __check(self, data: Message, obj: KEYWORDS) -> Verify:
        methods = {
            str: MessageMatch.check_str,
            equal: MessageMatch.check_equal,
            re.Pattern: MessageMatch.check_reg
        }
        t = type(obj)

        if t in methods.keys():
            method = methods[t]
            check = Verify(*method(data, obj))
            if check:
                return check

        elif t is list:
            for item in obj:
                check = self.__check(data, item)
                if check:
                    return check

        return Verify(False)

    async def verify(self, data: Message):
        flag = False
        if self.check_prefix:
            for word in (self.check_prefix if type(self.check_prefix) is list else BotHandlers.prefix_keywords):
                if data.text_origin.startswith(word):
                    flag = True
                    break

        if self.check_prefix and not flag and not type(self.keywords) is equal:
            equal_filter = [n for n in self.keywords if type(n) is equal] if type(self.keywords) is list else []
            if equal_filter:
                self.keywords = equal_filter
            else:
                return Verify(False)

        if self.custom_verify:
            result = await self.custom_verify(data)

            if type(result) is bool:
                result = result, int(result), []

            elif type(result) is tuple:
                contrast = result[0], int(result[0]), []
                result = (result + contrast[len(result):])[:3]

            return Verify(*result)

        return self.__check(data, self.keywords)

    async def action(self, data: Message):
        return await self.function(data)


class BotHandlers:
    prefix_keywords: List[str] = list()

    private_message_handlers: List[Handler] = list()
    group_message_handlers: List[Handler] = list()
    temp_message_handlers: List[Handler] = list()
    event_handlers: Dict[str, List[EVENT_CORO]] = dict()

    overspeed_handler: Optional[FUNC_CORO] = None
    message_middleware: Optional[MIDDLE_WARE] = None

    @classmethod
    def detail(cls):
        return [
            f'- private_message_handlers ({len(cls.private_message_handlers)})',
            f'- group_message_handlers ({len(cls.group_message_handlers)})',
            f'- temp_message_handlers ({len(cls.temp_message_handlers)})',
            f'- event_handlers ({len(cls.event_handlers)})',
            f'- timed_tasks ({len(TasksControl.timed_tasks)})'
        ]

    @classmethod
    def add_prefix(cls, words: Union[str, List[str]]):
        """
        添加前缀触发词，在存在前缀触发词的情况下，handlers 会默认检查前缀

        :param words: 触发词，允许为一个触发词列表
        :return:
        """
        if type(words) is str:
            words = [words]
        cls.prefix_keywords += words

    @classmethod
    def handler_register(cls,
                         function_id: str,
                         handlers: List[Handler],
                         keywords: KEYWORDS = None,
                         verify: VERIFY_CORO = None,
                         check_prefix: PREFIX = True):
        """
        功能注册器工厂函数

        :param function_id:   功能ID
        :param handlers:      注册目标
        :param keywords:      触发关键字
        :param verify:        自定义校验方法
        :param check_prefix:  是否校验前缀或指定需要校验的前缀
        :return:              注册函数的装饰器
        """

        def register(func: FUNC_CORO):
            _handler = Handler(function_id, func, check_prefix=check_prefix)

            if verify:
                _handler.custom_verify = verify
            else:
                _handler.keywords = keywords

            handlers.append(_handler)

        return register

    @classmethod
    def on_private_message(cls,
                           function_id: str = None,
                           keywords: KEYWORDS = None,
                           verify: VERIFY_CORO = None,
                           check_prefix: PREFIX = False):
        """
        注册一个私聊消息的功能
        功能函数接受一个 Message 参数，内含消息的内容以及回复等操作，允许返回一个 Chain 对象进行回复

        :param function_id:   功能ID，不唯一，仅用于记录该功能的使用数量
        :param keywords:      触发关键字，支持字符串、正则、全等句（equal）或由它们构成的列表
        :param verify:        自定义校验方法，当该参数被赋值时，keywords 将会失效
        :param check_prefix:  是否校验前缀或指定需要校验的前缀
        :return:              功能注册器工厂函数
        """
        return cls.handler_register(function_id, cls.private_message_handlers, keywords, verify, check_prefix)

    @classmethod
    def on_group_message(cls,
                         function_id: str = None,
                         keywords: KEYWORDS = None,
                         verify: VERIFY_CORO = None,
                         check_prefix: PREFIX = True):
        """
        注册一个群组消息的功能
        功能函数接受一个 Message 参数，内含消息的内容以及回复等操作，允许返回一个 Chain 对象进行回复

        :param function_id:   功能ID，不唯一，仅用于记录该功能的使用数量
        :param keywords:      触发关键字，支持字符串、正则、全等句（equal）或由它们构成的列表
        :param verify:        自定义校验方法，当该参数被赋值时，keywords 将会失效
        :param check_prefix:  是否校验前缀或指定需要校验的前缀
        :return:              功能注册器工厂函数
        """
        return cls.handler_register(function_id, cls.group_message_handlers, keywords, verify, check_prefix)

    @classmethod
    def on_temp_message(cls,
                        function_id: str = None,
                        keywords: KEYWORDS = None,
                        verify: VERIFY_CORO = None,
                        check_prefix: PREFIX = True):
        """
        注册一个临时聊天的功能
        功能函数接受一个 Message 参数，内含消息的内容以及回复等操作，允许返回一个 Chain 对象进行回复

        :param function_id:   功能ID，不唯一，仅用于记录该功能的使用数量
        :param keywords:      触发关键字，支持字符串、正则、全等句（equal）或由它们构成的列表
        :param verify:        自定义校验方法，当该参数被赋值时，keywords 将会失效
        :param check_prefix:  是否校验前缀或指定需要校验的前缀
        :return:              功能注册器工厂函数
        """
        return cls.handler_register(function_id, cls.temp_message_handlers, keywords, verify, check_prefix)

    @classmethod
    def on_event(cls, event):
        """
        事件处理注册器工厂函数
        处理函数接受一个 Event 参数，内含事件的内容，允许返回一个 Chain 对象进行消息发送

        注意：同一个事件名能拥有多个处理函数，这是出于灵活处理考虑，在注册时请避免冲突的操作

        :param event: 监听的事件，可传入 MiraiEvents 的属性类或事件名的字符串
        :return:      注册函数的装饰器
        """

        def handler(func: EVENT_CORO):
            if issubclass(event, Event):
                event_name = event.__name__
            else:
                if type(event) is str:
                    event_name = event
                else:
                    raise TypeError('Event must be property of MiraiEvents or string of event name.')

            if event_name not in cls.event_handlers:
                cls.event_handlers[event_name] = []

            cls.event_handlers[event_name].append(func)

        return handler

    @classmethod
    def on_overspeed(cls, hanlder: FUNC_CORO):
        """
        处理触发消息速度限制的事件，只允许存在一个

        :param hanlder: 处理函数
        :return:
        """
        if not cls.overspeed_handler:
            cls.overspeed_handler = hanlder
        else:
            raise Exception('Only one overspeed handler can exist.')

    @classmethod
    def handle_message(cls, hanlder: MIDDLE_WARE):
        """
        Message 对象与消息处理器的中间件，用于对 Message 作进一步的客制化处理，只允许存在一个

        :param hanlder: 处理函数
        :return:
        """
        if not cls.message_middleware:
            cls.message_middleware = hanlder
        else:
            raise Exception('Only one message middleware can exist.')


on_private_message = BotHandlers.on_private_message
on_group_message = BotHandlers.on_group_message
on_temp_message = BotHandlers.on_temp_message
on_event = BotHandlers.on_event
on_overspeed = BotHandlers.on_overspeed
handle_message = BotHandlers.handle_message
timed_task = TasksControl.timed_task