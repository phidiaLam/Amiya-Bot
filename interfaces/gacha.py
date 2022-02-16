from typing import List
from fastapi import File, UploadFile
from core.util import create_dir
from core.network import response
from core.network.httpServer.auth import AuthManager
from core.database import SearchParams, select_for_paginate, model_to_dict
from core.resource.arknightsGameData import ArknightsGameData

from .model.pool import PoolTable, PoolInfo
from functions.arknights.gacha.gacha import Pool as PoolBase, PoolSpOperator


class Pool:
    @classmethod
    async def get_pools_by_pages(cls, items: PoolTable, auth=AuthManager.depends()):
        search = SearchParams(
            items.search,
            contains=['limit_pool', 'pool_name']
        )

        data, count = select_for_paginate(PoolBase,
                                          search,
                                          order_by=(PoolBase.id.desc(),),
                                          page=items.page,
                                          page_size=items.pageSize)

        data = {item['id']: item for item in data}

        sp_list: List[PoolSpOperator] = PoolSpOperator.select().where(
            PoolSpOperator.pool_id.in_(list(data.keys()))
        )

        for item in sp_list:
            _id = item.pool_id.id
            if _id in data and 'sp_list' not in data[_id]:
                data[_id]['sp_list'] = []
            data[_id]['sp_list'].append(model_to_dict(item))

        return response({'count': count, 'data': [item for i, item in data.items()]})

    @classmethod
    async def add_new_pool(cls, items: PoolInfo, auth=AuthManager.depends()):
        check = PoolBase.get_or_none(pool_name=items.pool_name)
        if check:
            return response(message='卡池已存在')

        pool: PoolBase = PoolBase.create(
            pickup_4=items.pickup_4,
            pickup_5=items.pickup_5,
            pickup_6=items.pickup_6,
            pickup_s=items.pickup_s,
            limit_pool=items.limit_pool,
            pool_name=items.pool_name
        )

        sp = []
        for item in items.sp_list:
            sp.append({
                'pool_id': pool.id,
                'operator_name': item.operator_name,
                'rarity': item.rarity,
                'classes': item.classes,
                'image': item.image
            })

        PoolSpOperator.insert_data(sp)

        return response(message='添加成功')

    @classmethod
    async def edit_pool(cls, items: PoolInfo, auth=AuthManager.depends()):
        pool: PoolBase = PoolBase.get_or_none(pool_name=items.pool_name)
        if not pool:
            return response(message='卡池不存在')

        PoolBase.update(
            pickup_4=items.pickup_4,
            pickup_5=items.pickup_5,
            pickup_6=items.pickup_6,
            pickup_s=items.pickup_s,
            limit_pool=items.limit_pool
        ).where(
            PoolBase.id == pool.id
        ).execute()

        sp = []
        for item in items.sp_list:
            sp.append({
                'pool_id': pool.id,
                'operator_name': item.operator_name,
                'rarity': item.rarity,
                'classes': item.classes,
                'image': item.image
            })

        PoolSpOperator.delete().where(PoolSpOperator.pool_id == pool.id).execute()
        PoolSpOperator.insert_data(sp)

        return response(message='修改成功')

    @classmethod
    async def del_pool(cls, items: PoolInfo, auth=AuthManager.depends()):
        pool: PoolBase = PoolBase.get_or_none(pool_name=items.pool_name)
        if not pool:
            return response(message='卡池不存在')

        PoolBase.delete().where(PoolBase.id == pool.id).execute()

        return response(message='删除成功')

    @classmethod
    async def upload_image(cls, file: UploadFile = File(...), auth=AuthManager.depends()):
        content = await file.read()
        path = 'resource/images/temp'

        create_dir(path)

        with open(f'{path}/{file.filename}', mode='wb') as f:
            f.write(content)

        return response(data={'filename': file.filename}, message='上传成功')


class Operator:
    @classmethod
    async def get_all_operator(cls, auth=AuthManager.depends()):
        operators = []

        for name, item in ArknightsGameData().operators.items():
            operators.append(
                {
                    'name': name,
                    'en_name': item.en_name,
                    'class': item.classes,
                    'classes_sub': item.classes_sub,
                    'rarity': item.rarity
                }
            )

        return response(operators)