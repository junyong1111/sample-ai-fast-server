from setuptools import setup, find_packages

setup(
    name="sample-ai-fast-server",
    version="0.1.0",
    author="devjun",
    author_email="jyporse@naver.com",
    description="A FastAPI application with JWT authentication",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.12",
    install_requires=[
        # FastAPI 관련
        "fastapi==0.115.9",
        "uvicorn[standard]==0.24.0",

        # 환경변수 관리
        "python-dotenv==1.1.0",

        # JWT 토큰 발급
        "python-jose[cryptography]==3.3.0",
        "passlib[bcrypt]==1.7.4",
        "PyJWT==2.8.0",

        # 데이터 검증
        "pydantic==2.11.5",
        "pydantic-settings==2.9.1",

        # 로깅
        "colorlog==6.9.0",

        #네트워크
        "httpx==0.27.2",
        "asyncio==3.4.3",

        # 업비트
        "pyupbit==0.2.34",

        # MongoDB 연동
        "pymongo==4.6.0",
        "motor==3.3.2",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.5b2",
            "isort>=5.9.3",
            "flake8>=3.9.2",
            "mypy>=0.910",
        ],
    },
)