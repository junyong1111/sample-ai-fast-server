"""
JSON 직렬화를 위한 안전한 데이터 변환 유틸리티
inf, -inf, nan 값을 JSON 호환 값으로 변환
"""

import math
from typing import Any, Dict, List, Union


def sanitize_for_json(data: Any) -> Any:
    """
    JSON 직렬화를 위해 inf, -inf, nan 값을 안전한 값으로 변환

    Args:
        data: 변환할 데이터 (dict, list, primitive 등)

    Returns:
        JSON 직렬화 가능한 안전한 데이터
    """
    if isinstance(data, dict):
        return {key: sanitize_for_json(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_json(item) for item in data]
    elif isinstance(data, float):
        if math.isnan(data):
            return 0.0
        elif math.isinf(data):
            return 999999.0 if data > 0 else -999999.0
        else:
            return data
    else:
        return data


def safe_json_serialize(data: Any) -> str:
    """
    안전한 JSON 직렬화

    Args:
        data: 직렬화할 데이터

    Returns:
        JSON 문자열
    """
    import json
    sanitized_data = sanitize_for_json(data)
    return json.dumps(sanitized_data, ensure_ascii=False, default=str)
