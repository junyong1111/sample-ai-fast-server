from fastapi import FastAPI
from playwright.async_api import async_playwright
from .url import blog_router, user_router, autotrading_v2_router, information_router

import logging
import os
import traceback
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
import uvicorn
from src.common.utils.logger import set_logger
from src.common.error import JSendError, ErrorCode
from src.config.setting import settings
from src.package.db import init_pool, release_pool


async def startup():
    """애플리케이션 시작 시 실행"""
    # Playwright 시작
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(args=["--no-sandbox"])
    context = await browser.new_context(locale="ko-KR", device_scale_factor=1.0, offline=False)
    app.state.pw = pw
    app.state.browser = browser
    app.state.context = context

    try:
        # PostgreSQL 서비스 설정 및 연결
        await init_pool()
        logger.info(f"[PostgreSQL 연결 성공] {settings.POSTGRESQL_DB_HOST}:{settings.POSTGRESQL_DB_PORT}/{settings.POSTGRESQL_DB_DATABASE}")
    except Exception as e:
        logger.error(f"""
                        [PostgreSQL 연결 실패]
                        error : {e.__class__.__name__}
                        message : {e}
                    """)

async def shutdown():
    """애플리케이션 종료 시 실행"""
    try:
        # Playwright 종료
        await app.state.context.close()
        await app.state.browser.close()
        await app.state.pw.stop()
    except Exception:
        pass

    try:
        await release_pool()
    except Exception as e:
        logger.error(f"""
                        [PostgreSQL 연결 해제 실패]
                        error : {e.__class__.__name__}
                        message : {e}
                    """)

# 로깅 설정
log_dir = "../logs"
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(log_dir, "app.log"), encoding="utf-8")
    ]
)
logger = set_logger("exception")
# 전역 서비스 인스턴스
global_vector_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 시 실행"""

    logger.info("FastAPI 시작")
    await startup()

    # 전역 서비스 초기화
    try:
        logger.info(
            f"""
                [전역 서비스 초기화 완료]
            """)
    except Exception as e:
        logger.error(f"""
                        [전역 서비스 초기화 실패]
                        error : {e.__class__.__name__}
                        message : {e}
                    """)
        raise

    yield
    await shutdown()

    logger.info(
        f"""
            [FastAPI 종료]
        """)


# FastAPI 앱 생성
app = FastAPI(
    title="Sample AI Fast API",
    description="Sample AI Fast API",
    version="2.0.0",
    lifespan=lifespan
)

prefix_url = '/api/v2'
app.include_router(user_router.router, prefix=prefix_url)
app.include_router(autotrading_v2_router.router, prefix=prefix_url)
app.include_router(blog_router.router, prefix=prefix_url)
app.include_router(information_router.router, prefix=prefix_url)



# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 개발 서버 실행
if __name__ == "__main__":
    logger.info("🎯 서버 시작: http://localhost:8080")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )

@app.exception_handler(JSendError)
async def jsend_error_exception_handler(request: Request, exc: JSendError):
    logger.error(f"[{request.url}] JSendError {exc.__dict__}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=400,
        content={
            "status": exc.status,
            "code": exc.code,
            "message": exc.message,
            "data": exc.data,
        },
    )

@app.exception_handler(Exception)
async def unknown_error_exception_handler(request, exc: Exception):
    # 전체 스택 트레이스를 가져옴
    full_traceback = traceback.format_exc()

    # 줄바꿈으로 분할하여 리스트로 만듦
    traceback_lines = full_traceback.splitlines()

    # 마지막 5줄 | 10줄만 추출
    # last_five_lines_of_traceback = "\n".join(traceback_lines[-5:])
    last_five_lines_of_traceback = "\n".join(traceback_lines[-10:])
    logger.error(
        f"""
            [{request.url}] InternalError
            {last_five_lines_of_traceback}
        """
    )


    # 슬랙과 로거에 에러 메세지
    # if setting.SLACK_WEBHOOK_ENABLE == "on":
    #         await SLACK_LOGGER.application_in_critical_status_alarm(
    #         str(exc) + "\n\n" + last_five_lines_of_traceback
    #     )
    logger.exception(f"[{request.url}] InternalError\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "code": ErrorCode.Common.DEFAULT_ERROR[0],
            "message": ErrorCode.Common.DEFAULT_ERROR[1]
        }
    )
