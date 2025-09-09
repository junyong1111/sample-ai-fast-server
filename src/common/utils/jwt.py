from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import settings
from src.common.error import ErrorCode, JSendError
from src.package.db.connect import connection, transaction

SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS

KST = ZoneInfo("Asia/Seoul")

security = HTTPBearer()

async def get_current_user(
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_idx = payload.get("user_idx")
        user_id = payload.get("user_id")
        phone_number = payload.get("phone_number")
        payment_email = payload.get("payment_email")
        social_type = payload.get("social_type")
        membership_idx = payload.get("membership_idx")

        if user_idx is None:
            raise HTTPException(status_code=401, detail="Invalid JWT payload")
        # 필요하다면 DB에서 유저 정보 조회
        return {
            "user_idx": user_idx,
            "user_id": user_id,
            "membership_idx": membership_idx,
            "phone_number": phone_number,
            "payment_email": payment_email,
            "social_type": social_type,
        }
    except jwt.ExpiredSignatureError:
        raise JSendError(
            code=ErrorCode.Jwt.EXPIRED_ACCESS_TOKEN[0],
            message=ErrorCode.Jwt.EXPIRED_ACCESS_TOKEN[1],
        )
    except jwt.InvalidTokenError:
        raise JSendError(
            code=ErrorCode.Jwt.INVALID_ACCESS_TOKEN[0],
            message=ErrorCode.Jwt.INVALID_ACCESS_TOKEN[1],
        )

async def get_current_admin(
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")

        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid JWT payload")
        return {
            "user_id": user_id,
        }
    except jwt.ExpiredSignatureError:
        raise JSendError(
            code=ErrorCode.Jwt.EXPIRED_ACCESS_TOKEN[0],
            message=ErrorCode.Jwt.EXPIRED_ACCESS_TOKEN[1],
        )
    except jwt.InvalidTokenError:
        raise JSendError(
            code=ErrorCode.Jwt.INVALID_ACCESS_TOKEN[0],
            message=ErrorCode.Jwt.INVALID_ACCESS_TOKEN[1],
        )


async def create_access_token(
        data: dict,
        expires_delta: timedelta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    ):
    to_encode = data.copy()
    expire = datetime.now(KST) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def create_admin_access_token(
        data: dict,
        expires_delta: timedelta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    ):
    to_encode = data.copy()
    expire = datetime.now(KST) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt



async def create_refresh_token(
        data: dict,
        expires_delta: timedelta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    ):
    to_encode = data.copy()
    expire = datetime.now(KST) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def create_admin_refresh_token(
        data: dict,
        expires_delta: timedelta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    ):
    to_encode = data.copy()
    expire = datetime.now(KST) + expires_delta
    to_encode.update({"exp": expire})



async def save_refresh_token(user_idx: str, refresh_token: str):
    async with transaction() as trans:
        await trans.insert(
            "REPLACE INTO user_refresh_token (user_idx, refresh_token) VALUES (%s, %s)",
            (user_idx, refresh_token)
        )

async def get_refresh_token(user_idx: str):
    async with connection() as session:
        return await session.select_one(
            "SELECT refresh_token FROM user_refresh_token WHERE user_idx = %s",
            (user_idx,)
        )

async def delete_refresh_token(user_idx: str):
    async with transaction() as trans:
        await trans.delete(
            "DELETE FROM user_refresh_token WHERE user_idx = %s",
            (user_idx,)
        )


async def refresh_access_token(refresh_token: str):
    try:
        # 1. 리프레시 토큰 디코드
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_idx = payload.get("user_idx")
        if not user_idx:
            raise JSendError(
                code=ErrorCode.Jwt.INVALID_REFRESH_TOKEN[0],
                message=ErrorCode.Jwt.INVALID_REFRESH_TOKEN[1],
            )

        #TODO 추후에 리프레쉬 저장은 레디스로 이관 예정...
        # 2. DB에 저장된 리프레시 토큰과 비교
        # saved_token_row = await get_refresh_token(user_idx)
        # saved_token = saved_token_row["refresh_token"] if saved_token_row else None
        # if saved_token != refresh_token:
        #     raise JSendError(
        #         code=ErrorCode.Jwt.INVALID_REFRESH_TOKEN[0],
        #         message=ErrorCode.Jwt.INVALID_REFRESH_TOKEN[1],
        #     )

        # 3. 새 액세스 토큰 발급
        new_access_token = await create_access_token(
            data={
                "user_id": payload.get("user_id"),
                "user_idx": payload.get("user_idx"),
                "membership_idx": payload.get("membership_idx"),
                "phone_number": payload.get("phone_number"),
                "payment_email": payload.get("payment_email"),
                "social_type": payload.get("social_type"),
                "is_integrated": payload.get("is_integrated"),
            }
        )
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    except jwt.ExpiredSignatureError:
        raise JSendError(
            code=ErrorCode.Jwt.EXPIRED_ACCESS_TOKEN[0],
            message=ErrorCode.Jwt.EXPIRED_ACCESS_TOKEN[1],
        )
    except jwt.InvalidTokenError:
        raise JSendError(
            code=ErrorCode.Jwt.INVALID_ACCESS_TOKEN[0],
            message=ErrorCode.Jwt.INVALID_ACCESS_TOKEN[1],
        )


async def refresh_admin_access_token(refresh_token: str):
    try:
        # 1. 리프레시 토큰 디코드
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        user_idx = payload.get("user_idx")
        if not user_id or not user_idx:
            raise JSendError(
                code=ErrorCode.Jwt.INVALID_REFRESH_TOKEN[0],
                message=ErrorCode.Jwt.INVALID_REFRESH_TOKEN[1],
            )


        # 3. 새 액세스 토큰 발급
        new_access_token = await create_access_token(
            data={
                "user_id": payload.get("user_id"),
                "user_idx": payload.get("user_idx"),
            }
        )
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    except jwt.ExpiredSignatureError:
        raise JSendError(
            code=ErrorCode.Jwt.EXPIRED_ACCESS_TOKEN[0],
            message=ErrorCode.Jwt.EXPIRED_ACCESS_TOKEN[1],
        )
    except jwt.InvalidTokenError:
        raise JSendError(
            code=ErrorCode.Jwt.INVALID_ACCESS_TOKEN[0],
            message=ErrorCode.Jwt.INVALID_ACCESS_TOKEN[1],
        )