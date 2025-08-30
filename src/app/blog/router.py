from fastapi import APIRouter, Depends, Request
from src.app.blog.model import RenderIn
from src.app.blog import service as blog_service

router = APIRouter(tags=["blog"])

@router.post(
    "/render",
    summary="Render blog",
    description="Render blog",
)
async def render(
    input_data: RenderIn,
    request: Request,
    blog_service: blog_service.BlogService = Depends(blog_service.BlogService)
):
    return await blog_service.render(
        app=request.app,
        html=input_data.html
    )

@router.get("/health")
async def health():
    return {"ok": True}


