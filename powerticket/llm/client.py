"""DashScope qwen 客户端（openai 兼容模式，决策 D-2，plan/06）。

core 零三方依赖：openai 懒加载，仅在本模块触达（依赖入 extras[llm]）；
密钥走环境变量 DASHSCOPE_API_KEY 或仓库根 .env（.gitignore 已排除，不入仓）；
enable_thinking=false 为既定口径；模型/接入点/超时可用环境变量覆盖。

任何不可用（依赖未装 / 密钥未配 / 网络 / 坏响应）抛 LLMUnavailable，调用方降级纯规则通路。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import LLMUnavailable

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOTENV = _REPO_ROOT / ".env"

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-plus"
DEFAULT_TIMEOUT = 30.0

API_KEY_ENV = "DASHSCOPE_API_KEY"
MODEL_ENV = "POWERTICKET_LLM_MODEL"
BASE_URL_ENV = "POWERTICKET_LLM_BASE_URL"
TIMEOUT_ENV = "POWERTICKET_LLM_TIMEOUT"


def load_dotenv(path: Path = None, override: bool = False) -> Dict[str, str]:
    """极简 .env 读取（零依赖）：KEY=VALUE、# 注释/行内注释、去成对引号；默认不覆盖已有环境变量。"""
    path = Path(path) if path else DEFAULT_DOTENV
    loaded: Dict[str, str] = {}
    if not path.is_file():
        return loaded
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.split("#", 1)[0].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if not key:
            continue
        loaded[key] = value
        if override or key not in os.environ:
            os.environ[key] = value
    return loaded


def resolve_api_key(dotenv_path: Path = None) -> Optional[str]:
    """密钥解析：环境变量优先，其次仓库根 .env；都没有返回 None。"""
    load_dotenv(dotenv_path)
    value = os.environ.get(API_KEY_ENV, "").strip()
    return value or None


def _env_timeout() -> float:
    raw = os.environ.get(TIMEOUT_ENV, "").strip()
    try:
        return float(raw) if raw else DEFAULT_TIMEOUT
    except ValueError:
        return DEFAULT_TIMEOUT


def chat(
    messages: List[Dict[str, str]],
    *,
    api_key: str = None,
    model: str = None,
    base_url: str = None,
    timeout: float = None,
    client: Any = None,
) -> str:
    """单轮对话 → 助手文本；任何不可用抛 LLMUnavailable（调用方降级规则通路）。

    client 参数供测试注入假客户端（免网络离线覆盖正常路径）。
    """
    key = api_key or resolve_api_key()
    if not key:
        raise LLMUnavailable(f"未配置 {API_KEY_ENV}（环境变量或仓库根 .env）")

    if client is None:
        try:
            from openai import OpenAI  # 懒加载：core 不依赖 openai
        except ImportError as exc:
            raise LLMUnavailable("openai 依赖未安装（安装：py -m pip install -e .[llm]）") from exc
        try:
            client = OpenAI(
                api_key=key,
                base_url=base_url or os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL,
                timeout=timeout if timeout is not None else _env_timeout(),
            )
        except Exception as exc:
            raise LLMUnavailable(f"LLM 客户端初始化失败: {exc}") from exc

    model_name = model or os.environ.get(MODEL_ENV) or DEFAULT_MODEL
    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
            extra_body={"enable_thinking": False},  # 决策 D-2：关闭思考链
        )
    except LLMUnavailable:
        raise
    except Exception as exc:
        raise LLMUnavailable(f"LLM 调用失败: {exc}") from exc

    try:
        content = resp.choices[0].message.content
    except (AttributeError, IndexError) as exc:
        raise LLMUnavailable("LLM 响应结构异常（无 choices/message）") from exc
    if not content or not str(content).strip():
        raise LLMUnavailable("LLM 返回空内容")
    return str(content)
