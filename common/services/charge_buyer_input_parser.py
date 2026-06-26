"""
买家备注解析工具

闲鱼买家在订单备注中按"key=value 换行"格式填写代刷参数，例如：

    作品链接=https://www.douyin.com/video/7444444444444444444
    备注=尽快发

解析规则（容错优先）：
- 行内首个 "=" 或 "：" 或 ":" 作为分隔符
- 全角等号/冒号都接受（中文键盘常输全角）
- 多余的空白行/前后空格自动去除
- 同一 key 多次出现，后者覆盖前者
- 单纯一个 URL（无 key=）：当 fallback_url_key 提供时，自动赋给该 key

为什么不强制 JSON：买家不会写 JSON，闲鱼备注框里 quote/换行都会被吞
"""
from __future__ import annotations

import re


URL_PATTERN = re.compile(r"https?://[^\s\u4e00-\u9fa5]+", re.IGNORECASE)
SEPARATOR_PATTERN = re.compile(r"[=＝：:]", re.UNICODE)


def parse_buyer_remark(text: str | None, *, fallback_url_key: str | None = None) -> dict[str, str]:
    if not text:
        return {}

    result: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.lower().startswith(("http://", "https://")):
            continue
        match = SEPARATOR_PATTERN.search(line)
        if not match:
            continue
        key = line[: match.start()].strip()
        value = line[match.end() :].strip()
        if key and value:
            result[key] = value

    if not result and fallback_url_key:
        url_match = URL_PATTERN.search(text)
        if url_match:
            result[fallback_url_key] = url_match.group(0).strip()

    return result


def validate_required_keys(
    parsed: dict[str, str],
    required: list[str] | None,
) -> list[str]:
    if not required:
        return []
    return [k for k in required if not parsed.get(k, "").strip()]
