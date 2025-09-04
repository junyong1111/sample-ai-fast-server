import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Tuple

from redis.asyncio import ConnectionPool, Redis

from src.common.conf import setting
from src.common.constant import Constant

# from src.common.constant import Constants
from src.common.util.logger import set_logger

LOGGER = set_logger("redis")


class RedisPool:
    def __init__(
        self,
        redis_settings
    ):
        self.redis_settings = json.loads(redis_settings)
        self.pools: Dict[int, ConnectionPool | None] = {}
        self.last_used = {}  # 마지막 사용 시간 추적
        self.connection_ids = {}  # 각 db의 연결 ID 추적

    async def init(
        self,
        max_pool_size: int,
        idle_timeout: int = 600  # 10분
    ):
        database = self.redis_settings['databases'][setting.REDIS_DB]
        connection_id = str(uuid.uuid4())[:8]  # 8자리 고유 ID 생성
        self.connection_ids[database] = connection_id

        self.pools[database] = ConnectionPool(
            host=self.redis_settings['host'],
            port=self.redis_settings['port'],
            db=database,
            password=self.redis_settings['password'],
            max_connections=max_pool_size,
            decode_responses=True,
            socket_timeout=idle_timeout,
            socket_connect_timeout=30,
            retry_on_timeout=True,
            health_check_interval=30
        )

        LOGGER.info(f"Redis connection initialized - ID: {connection_id}, DB: {database}")

    async def get_pool_stats(self):
        stats = {}
        for db, pool in self.pools.items():
            if pool:
                stats[db] = {
                    "in_use": len(pool._in_use_connections),
                    "available": len(pool._available_connections),
                    "max": pool.max_connections
                }
        return stats

    async def cleanup_idle(self):
        current_time = datetime.now()
        for db, pool in self.pools.items():
            if pool and (current_time - self.last_used.get(db, current_time)).seconds > 600:
                try:
                    connection_id = self.connection_ids.get(db, "unknown")
                    await pool.aclose()
                    self.pools[db] = None
                    LOGGER.info(f"Redis connection closed due to idle - ID: {connection_id}, DB: {db}, Idle time: {(current_time - self.last_used[db]).seconds}s")
                except Exception as e:
                    LOGGER.error(f"Failed to close Redis connection - ID: {connection_id}, DB: {db}, Error: {str(e)}")

    async def get(self, db):
        if db is None:
            db = setting.REDIS_DB
        LOGGER.info(f"Attempting to get Redis pool for DB: {db}")

        if db not in self.pools:
            LOGGER.error(f"DB {db} not initialized in pools: {list(self.pools.keys())}")
            raise Exception(f"'db ({db})' not initialize.")

        # 연결이 사용될 때마다 last_used 시간 업데이트
        self.last_used[db] = datetime.now()
        # connection_id = self.connection_ids.get(db, "unknown")
        # LOGGER.debug(f"Redis connection accessed - ID: {connection_id}, DB: {db}")
        return self.pools[db]

    async def release(self):
        for db, pool in self.pools.items():
            if pool is None:
                continue
            try:
                connection_id = self.connection_ids.get(db, "unknown")
                await pool.aclose()
                LOGGER.info(f"Redis connection released - ID: {connection_id}, DB: {db}")
            except Exception as e:
                LOGGER.error(f"Failed to release Redis connection - ID: {connection_id}, DB: {db}, Error: {str(e)}")


redis_pool = RedisPool(redis_settings=setting.REDIS)


async def init_pool(
    # max_pool_size: int = 10,
    max_pool_size: int = 200, # 최대 커넥션 20000 / 현재 핫파 서버에 구니콘 워커수 10개에서 뒤에서 0 빼서 -> 일단 200개로 설정
):
    await redis_pool.init(
        max_pool_size=max_pool_size,
    )


async def release_pool():
    await redis_pool.release()


async def get_all_keys(db: int) -> List[str]:
    pool = await redis_pool.get(db=db)
    async with Redis(connection_pool=pool, decode_responses=True) as redis_conn:
        return await redis_conn.keys()


async def get_all_value(
    db: int,
    json_loads: bool = True
):
    pool = await redis_pool.get(db=db)
    async with Redis(connection_pool=pool, decode_responses=True) as redis_conn:
        key_value_list: List[Tuple] = []
        async for key in redis_conn.scan_iter(match="*"):
            value = await redis_conn.get(key)
            if json_loads:
                try:
                    key_value_list.append((key, json.loads(value)))
                except Exception as e:
                    key_value_list.append((key, value))
            else:
                key_value_list.append((key, value))

        return key_value_list


async def set_value(
    db: int = setting.REDIS_DB,
    key: Any = None,
    value: Any = None,
    expire_time: int = 0,
):
    if value is None:
        value = ""

    # Record 객체나 복잡한 객체를 딕셔너리로 변환
    if hasattr(value, '__dict__'):
        value = dict(value.__dict__)
    elif hasattr(value, '_asdict'):  # namedtuple이나 Record 타입 처리
        value = dict(value._asdict())

    # 딕셔너리 내부의 Record 객체들도 처리
    if isinstance(value, dict):
        value = {k: dict(v.__dict__) if hasattr(v, '__dict__') else v
                for k, v in value.items()}
    elif isinstance(value, list):
        value = [dict(item.__dict__) if hasattr(item, '__dict__') else item
                for item in value]

    # JSON 직렬화
    try:
        if isinstance(value, (dict, list)):
            value = json.dumps(value, default=lambda o: dict(o.__dict__) if hasattr(o, '__dict__') else str(o))
    except TypeError as e:
        LOGGER.error(f"JSON serialization error: {str(e)}, value type: {type(value)}")
        # 직렬화 실패시 문자열로 변환
        value = str(value)

    pool = await redis_pool.get(db=db)
    async with Redis(connection_pool=pool, decode_responses=True, socket_timeout=10) as redis_conn:
        if expire_time > 0:
            await redis_conn.setex(key, expire_time, value)
        else:
            await redis_conn.set(key, value)

        return pool, redis_conn


async def get_value(
    db: int = setting.REDIS_DB,
    key: str = "",
):
    pool = await redis_pool.get(db=db)
    async with Redis(connection_pool=pool, decode_responses=True, socket_timeout=10) as redis_conn:
        value = await redis_conn.get(key)
        if value:
            try:
                # 일반적인 JSON 파싱 시도
                if isinstance(value, str):
                    stripped = value.strip()
                    if (
                        (stripped.startswith('{') and stripped.endswith('}'))
                            or
                        (stripped.startswith('[') and stripped.endswith(']'))
                    ):
                        # return json.loads(value)
                        value_dict = json.loads(value)
                        for key, val in value_dict.items():
                            if isinstance(val, str) and val.startswith('<Record'):
                                # Record 문자열을 딕셔너리로 파싱
                                record_dict = {}
                                content = val.replace('<Record', '').replace('>', '').strip()
                                pairs = content.split()
                                for pair in pairs:
                                    if '=' in pair:
                                        k, v = pair.split('=', 1)
                                        v = v.strip('"\'')
                                        record_dict[k] = v
                                value_dict[key] = record_dict
                        return value_dict
                return json.loads(value)
            except json.JSONDecodeError:
                return value
            except Exception as e:
                LOGGER.error(f"Error parsing Redis value: {str(e)}")
                return value
        return value


# async def get_values_in_list_by_keys(
#     db: int = setting.REDIS_DB,
#     meta_key_list: List[str] = [],
# ):
#     pool = await redis_pool.get(db=db)
#     async with Redis(connection_pool=pool, decode_responses=True) as redis_conn:
#         values = []
#         for key in meta_key_list:
#             type = await redis_conn.type(key)
#             if type == Constants.Meta.DataType.STRING:
#                 values.append({key : await redis_conn.get(key)})
#             elif type == Constants.Meta.DataType.LIST:
#                 values.append({key : await redis_conn.lrange(key, 0, -1)})
#             elif type == Constants.Meta.DataType.HASH:
#                 values.append({key : await redis_conn.hgetall(key)})
#             else:
#                 # raise Exception(f"Not supported data type ({type})")
#                 values.append({key : None})

#         return values


# async def get_ttl(
#     db: int,
#     key: str,
# ):
#     pool = await redis_pool.get(db=db)
#     async with Redis(connection_pool=pool, decode_responses=True) as redis_conn:
#         ttl = await redis_conn.ttl(key)
#         if ttl == -1:
#             raise Exception("Not set expire setting.")

#         if ttl == -2:
#             raise Exception(f"No exist key ({key}) in db ({db}).")

#         return ttl


async def set_ttl(
    db: int,
    key: str,
    expire_time: int = 0
):
    pool = await redis_pool.get(db=db)
    async with Redis(connection_pool=pool, decode_responses=True) as redis_conn:
        await redis_conn.expire(key, expire_time)  # expire_time을 설정


async def hset_value(
    db: int = setting.REDIS_DB,
    key: str = "",
    field: str = "",
    value: Any = None,
    # data_type: str = Constants.Meta.DataType.STRING,
):
    pool = await redis_pool.get(db=db)
    async with Redis(connection_pool=pool, decode_responses=True) as redis_conn:
        return await redis_conn.hset(key, field, value)


async def hget_value(
    db: int = setting.REDIS_DB,
    key: str = "",
    field: str = "",
    # data_type: str = Constants.Meta.DataType.STRING,
):
    pool = await redis_pool.get(db=db)
    async with Redis(connection_pool=pool, decode_responses=True) as redis_conn:
        return await redis_conn.hget(key, field)


async def hget_all(
    db: int = setting.REDIS_DB,
    key: str = "",
    data_type: str = Constant.DataType.STRING,
):
    pool = await redis_pool.get(db=db)
    async with Redis(connection_pool=pool, decode_responses=True) as redis_conn:
        res = await redis_conn.hgetall(key)

        if data_type == Constant.DataType.INT:
            res = {k: int(v) for k, v in res.items()}
        if data_type == Constant.DataType.BOOL:
            # res = {k: bool(v) for k, v in res.items()}
            res = {k: v.lower() == 'true' for k, v in res.items()}
        if data_type == Constant.DataType.HASH:
            # res = {k: json.loads(v) for k, v in res.items()}
            # 안전한 json 파싱 처리
            res = {
                k: json.loads(v) if isinstance(v, (str, bytes)) else v
                for k, v in res.items()
            }
        # return await redis_conn.hgetall(key)
        return res


async def lpush_value(
    db: int = setting.REDIS_DB,
    key: str = "",
    value: Any = None,
):
    pool = await redis_pool.get(db=db)
    async with Redis(connection_pool=pool, decode_responses=True) as redis_conn:
        return await redis_conn.lpush(key, value)


async def lset_value(
    db: int = setting.REDIS_DB,
    key: str = "",
    index: int = 0,
    value: Any = None,
):
    pool = await redis_pool.get(db=db)
    async with Redis(connection_pool=pool, decode_responses=True) as redis_conn:
        return await redis_conn.lset(key, index, value)


async def lrem_value(
    db: int = setting.REDIS_DB,
    key: str = "",
    count: int = 0,
    value: Any = None,
):
    pool = await redis_pool.get(db=db)
    async with Redis(connection_pool=pool, decode_responses=True) as redis_conn:
        return await redis_conn.lrem(key, count, value)

async def rpop_value(
    db: int = setting.REDIS_DB,
    key: str = "",
):
    """
    Redis 리스트의 오른쪽(끝)에서 요소를 제거하고 반환합니다.

    Args:
        db (int): Redis 데이터베이스 번호
        key (str): 리스트의 키

    Returns:
        Any: 리스트의 마지막 요소. 리스트가 비어있으면 None 반환
    """
    pool = await redis_pool.get(db=db)
    async with Redis(connection_pool=pool, decode_responses=True) as redis_conn:
        return await redis_conn.rpop(key)


# async def lrange_value(
#     db: int = setting.REDIS_DB,
#     key: str = "",
#     start: int = 0,
#     end: int = -1,
#     data_type: str = Constants.Meta.DataType.STRING,
# ):
#     pool = await redis_pool.get(db=db)
#     async with Redis(connection_pool=pool, decode_responses=True) as redis_conn:
#         res = await redis_conn.lrange(key, start, end)

#         if data_type == Constants.Meta.DataType.INT:
#             res = [int(i) for i in res]

#         # return await redis_conn.lrange(key, start, end)
#         return res


async def delete_by_key(
    db: int = setting.REDIS_DB,
    key: str = ""
):
    pool = await redis_pool.get(db=db)
    async with Redis(connection_pool=pool, decode_responses=True) as redis_conn:
        return await redis_conn.delete(key)


async def delete_value_specific_field(
    db: int = setting.REDIS_DB,
    key: str = "",
    field: str = "",
):
    pool = await redis_pool.get(db=db)
    async with Redis(connection_pool=pool, decode_responses=True) as redis_conn:
        if field:  # 특정 필드가 주어지면 해당 필드만 삭제
            return await redis_conn.hdel(key, field)  # 해시에서 특정 필드 삭제
        return await redis_conn.delete(key)  # 키 전체 삭제


async def get_type(
    db: int = setting.REDIS_DB,
    key: str = ""
):
    pool = await redis_pool.get(db=db)
    async with Redis(connection_pool=pool, decode_responses=True) as redis_conn:
        return await redis_conn.type(key)


