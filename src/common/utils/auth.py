import hashlib


async def get_md5_hash(value: str) -> str:
    """
    md5 해시로 변환
    """
    return hashlib.md5(value.encode()).hexdigest()
