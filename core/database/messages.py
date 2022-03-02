import asyncio

from core.database import *
from core.builtin.message import Message
from core.control import StateControl
from core import log

db = sqlite(db_conf.message)


class MessageBaseModel(Model):
    class Meta:
        database = db


@table
class MessageRecord(MessageBaseModel):
    msg_type: str = TextField()
    user_id: int = BigIntegerField()
    group_id: int = BigIntegerField(null=True)
    text: str = TextField(null=True)
    face: str = TextField(null=True)
    image: str = TextField(null=True)
    message: str = TextField(null=True)
    classify: str = TextField(null=True)
    create_time: int = IntegerField()


class MessageStack:
    stack: List[dict] = []

    @classmethod
    async def run_recording(cls):
        while StateControl.alive:
            await asyncio.sleep(5)
            if cls.stack:
                async with log.catch('MessageStack Error:'):
                    MessageRecord.insert_data(cls.stack.copy())
                cls.stack = []

    @classmethod
    def insert(cls, item: Message, effective: bool = False):
        cls.stack.append({
            'msg_type': item.type,
            'user_id': item.user_id,
            'group_id': item.group_id,
            # 'text': item.text_origin,
            # 'face': ''.join([f'[face:{n}]' for n in item.face]),
            # 'image': ','.join([n for n in item.image if type(n) is str]),
            # 'message': json.dumps(item.message, ensure_ascii=False) if item.message else '',
            'classify': 'call' if effective else '',
            'create_time': item.time
        })
