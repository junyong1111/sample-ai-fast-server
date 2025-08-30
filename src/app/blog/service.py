import io
import re
from typing import List, Union
import zipfile
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from app.blog.model import RenderIn

# -------- 전처리: 코드펜스/개행/백슬래시 제거 --------
class BlogService:
    def __init__(self):
        pass

    @staticmethod
    async def clean_html(
            raw: str
        ) -> str:
        s = raw
        # 앞뒤 ```(언어) 코드펜스 제거
        s = re.sub(r"^\s*```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s)
        # 개행 제거
        s = s.replace("\r", "").replace("\n", "")
        # 백슬래시 제거
        s = s.replace("\\", "")
        return s.strip()

    @staticmethod
    async def render(
        app: FastAPI,
        html: Union[str, List[str]],
    ) -> StreamingResponse:
        if isinstance(html, list):
            if not html:
                raise HTTPException(400, "빈 리스트입니다.")
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for idx, raw in enumerate(html):
                    html = await BlogService.clean_html(raw)
                    if not html:
                        continue
                    img = await BlogService.render_one(app, html)
                    zf.writestr(f"render_{idx}.png", img)
            buf.seek(0)
            return StreamingResponse(buf, media_type="application/zip",
                                    headers={"Content-Disposition": 'attachment; filename="renders.zip"'})
        else:
            html = await BlogService.clean_html(html)
            if not html:
                raise HTTPException(400, "빈 HTML입니다.")
            img = await BlogService.render_one(app, html)
            return StreamingResponse(io.BytesIO(img), media_type="image/png",
                                    headers={"Content-Disposition": 'inline; filename="render.png"'})


    @staticmethod
    async def render_one(
            app: FastAPI,
            html: str
        ) -> bytes:
        page = await app.state.context.new_page()
        try:
            # 기본 1200x800, 문서 전체 캡처
            await page.set_viewport_size({"width": 1200, "height": 800})
            await page.set_content(html, wait_until="networkidle")
            return await page.screenshot(full_page=True, type="png")
        finally:
            await page.close()

