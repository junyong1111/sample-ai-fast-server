from fastapi import FastAPI
from playwright.async_api import async_playwright

from src.app.url import blog_router, autotrading_router


app = FastAPI(title="HTML to Image (minimal)")

app.include_router(blog_router.router, prefix="/blog")
app.include_router(autotrading_router.router, prefix="/autotrading")


@app.on_event("startup")
async def startup():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(args=["--no-sandbox"])
    context = await browser.new_context(locale="ko-KR", device_scale_factor=1.0, offline=False)
    app.state.pw = pw
    app.state.browser = browser
    app.state.context = context

@app.on_event("shutdown")
async def shutdown():
    try:
        await app.state.context.close()
        await app.state.browser.close()
        await app.state.pw.stop()
    except Exception:
        pass

