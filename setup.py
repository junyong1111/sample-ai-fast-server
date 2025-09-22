from setuptools import setup, find_packages

setup(
    name="fastapi-app",                # 패키지 이름
    version="0.1.0",                   # 버전
    author="devjun",                   # 작성자
    author_email="jyporse@naver.com",  # 이메일
    description="FastAPI app for SNSHelp API integration",
    long_description_content_type="text/markdown",
    package_dir={"": "src"},           # 소스 디렉토리 위치
    packages=find_packages(where="src"),
    python_requires=">=3.12",
    install_requires=[
        "fastapi>=0.112.2",
        "uvicorn[standard]>=0.26.0",
        "pydantic>=2.7.1",
        "playwright>=1.46",
        "requests>=2.32.5",
        "httpx>=0.28.1",
        "motor>=3.3.2",                # MongoDB 비동기 드라이버
        "pymongo>=4.6.0",              # MongoDB 동기 드라이버
        "numpy>=2.2.3",                 # 수치 연산
        "pandas>=2.2.3",                # 데이터 분석
        "ccxt>=4.0.0",                  # 암호화폐 거래소 API (업비트, 바이낸스 등)
        "pydantic-settings>=2.5.2",

        #postgres db
        "asyncpg>=0.29.0",

        # 리스크 분석 에이전트 의존성
        "yfinance>=0.2.28",                    # 야후 파이낸스 데이터
        "langchain>=0.1.0",                    # 랭체인
        "langchain-openai>=0.1.0",             # OpenAI 통합
        "langgraph>=0.1.0",                    # 랭그래프
        "scipy>=1.11.0",                       # 상관관계 계산
        "scikit-learn>=1.3.0",                 # 머신러닝 유틸리티

        # 소셜 분석 에이전트 의존성
        "praw>=7.10.0",                        # Reddit API
        "requests>=2.32.5",                    # HTTP 요청
        "os>=0.1.0",                           # 운영체제 관련 유틸리티
        "asyncio>=3.4.3",                      # 비동기 프로그래밍
        "json>=2.0.9",                         # JSON 파싱
        "logging>=0.5.1.2",                    # 로깅
    ],
    entry_points={
        "console_scripts": [
            "fastapi-app=app.main:main",   # main 실행 엔트리포인트
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Framework :: FastAPI",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)