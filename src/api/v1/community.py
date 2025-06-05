from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, Query

from src.core.context import get_current_user_context
from src.dto.community import CommunityDetailResponse, CommunityListResponse
from src.exceptions.user import AuthenticationError
from src.services.community_service import CommunityService

from ...db.session import get_db

router = APIRouter()

@router.get("/list", response_model=CommunityListResponse)
async def list(
    page: int = 1,
    pageSize: int = 10,
    db: Session = Depends(get_db)
):
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    communityListData =  await CommunityService.query_community_list(db, user.id, page, pageSize)
    return CommunityListResponse(
        code=0,
        data=communityListData
    )

@router.get("/detail", response_model=CommunityDetailResponse)
async def detail(
    seoImgUid: str,
    db: Session = Depends(get_db)
):
    # 获取当前用户信息
    user = get_current_user_context()
    
    communityDetailData = await CommunityService.query_community_detail(db, seoImgUid, user.id if user else None)
    return CommunityDetailResponse(
        code=0,
        data=communityDetailData
    )
