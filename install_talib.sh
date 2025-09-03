#!/bin/bash

# TA-Lib 설치 스크립트
# macOS와 Linux에서 모두 작동

echo "🔧 TA-Lib 설치 시작..."

# 운영체제 확인
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "📱 macOS 감지"

    # Homebrew 설치 확인
    if ! command -v brew &> /dev/null; then
        echo "❌ Homebrew가 설치되지 않았습니다. 먼저 Homebrew를 설치해주세요."
        echo "https://brew.sh/"
        exit 1
    fi

    # TA-Lib 설치
    echo "📦 Homebrew로 TA-Lib 설치 중..."
    brew install ta-lib

elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    echo "🐧 Linux 감지"

    # Ubuntu/Debian
    if command -v apt-get &> /dev/null; then
        echo "📦 apt-get으로 TA-Lib 의존성 설치 중..."
        sudo apt-get update
        sudo apt-get install -y build-essential libta-lib-dev
    # CentOS/RHEL
    elif command -v yum &> /dev/null; then
        echo "📦 yum으로 TA-Lib 의존성 설치 중..."
        sudo yum groupinstall -y "Development Tools"
        sudo yum install -y ta-lib-devel
    else
        echo "❌ 지원되지 않는 Linux 배포판입니다."
        exit 1
    fi
else
    echo "❌ 지원되지 않는 운영체제입니다: $OSTYPE"
    exit 1
fi

# Python TA-Lib 설치
echo "🐍 Python TA-Lib 설치 중..."
pip install TA-Lib

# 설치 확인
echo "✅ 설치 확인 중..."
python -c "import talib; print(f'TA-Lib 버전: {talib.__version__}')"

if [ $? -eq 0 ]; then
    echo "🎉 TA-Lib 설치 완료!"
else
    echo "❌ TA-Lib 설치 실패"
    exit 1
fi
