"""Web Data Source service (Phase 6).

Pipeline: URL -> Crawler (httpx fetch) -> Parser -> Structured Extractor
(HTML tables / JSON) -> Dataset -> Governance Flow.

`transport` is injectable for tests (httpx MockTransport).
"""

import json
from io import BytesIO
from uuid import uuid4

import httpx
import pandas as pd
from loguru import logger

from app.schemas.dataset import DatasetInfo
from app.services.dataset_service import DatasetService


class WebSourceService:
    # 浏览器 User-Agent：绕过常见站点（Wikipedia 等）对非浏览器请求的 403
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport
        self._datasets = DatasetService()

    def fetch(self, url: str) -> tuple[bytes, str]:
        if self._transport is not None:
            with httpx.Client(transport=self._transport, headers=self.HEADERS) as client:
                resp = client.get(url, follow_redirects=True)
        else:
            resp = httpx.get(url, timeout=30.0, follow_redirects=True, headers=self.HEADERS)
        resp.raise_for_status()
        return resp.content, resp.headers.get("content-type", "")

    def parse(self, content: bytes, content_type: str) -> pd.DataFrame:
        """Structured Extractor: HTML table (first) or JSON -> DataFrame."""
        ctype = content_type.lower()
        if "json" in ctype:
            data = json.loads(content.decode("utf-8"))
            if isinstance(data, list):
                return pd.DataFrame(data)
            if isinstance(data, dict):
                return pd.json_normalize(data)
            raise ValueError("JSON must be an array or object")
        tables = pd.read_html(BytesIO(content))
        if not tables:
            raise ValueError("no <table> found in HTML content")
        return tables[0]

    def register(self, url: str) -> DatasetInfo:
        content, ctype = self.fetch(url)
        df = self.parse(content, ctype)
        name = url.split("//")[-1].split("/")[-1][:40] or "web"
        info = self._datasets.save_dataframe(f"web.{name}", df, source_type="web", name=name)
        logger.info(f"web source registered: {info.id} ({url}) {len(df)} rows")
        return info

    def register_batch(self, urls: list[str]) -> list[DatasetInfo]:
        infos = []
        for url in urls:
            try:
                infos.append(self.register(url))
            except Exception as exc:  # noqa: BLE001 - one bad URL must not kill the batch
                logger.warning(f"web register failed for {url}: {exc}")
        return infos
