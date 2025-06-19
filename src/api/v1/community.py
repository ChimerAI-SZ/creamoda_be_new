from sqlalchemy.orm import Session
from fastapi import Request
from fastapi import APIRouter, Depends, Query

from src.core.context import get_current_user_context
from src.dto.common import CommonResponse
from src.dto.community import CancelLikeRequest, CancelLikeResponse, CommunityDetailResponse, CommunityListResponse, LikeRequest, LikeResponse, ShareRequest, ShareResponse
from src.exceptions.user import AuthenticationError
from src.services.community_service import CommunityService
from src.services.like_img_service import LikeImgService
from src.utils.auth_util import get_user_info_from_request

from ...db.session import get_db

router = APIRouter()

@router.get("/list", response_model=CommunityListResponse)
async def list(
    request: Request,
    page: int = 1,
    pageSize: int = 10,
    db: Session = Depends(get_db)
):
    # 获取当前用户信息
    try:
        user = get_user_info_from_request(request)
    except Exception as e:
        user = None
    
    communityListData =  await CommunityService.query_community_list(db, user.id if user else None, page, pageSize)
    return CommunityListResponse(
        code=0,
        data=communityListData
    )

@router.get("/detail", response_model=CommunityDetailResponse)
async def detail(
    request: Request,
    seoImgUid: str,
    db: Session = Depends(get_db)
):
    # 获取当前用户信息
    try:
        user = get_user_info_from_request(request)
    except Exception as e:
        user = None
    
    communityDetailData = await CommunityService.query_community_detail(db, seoImgUid, user.id if user else None)
    return CommunityDetailResponse(
        code=0,
        data=communityDetailData
    )

@router.post("/like", response_model=LikeResponse)
async def like(
    request: LikeRequest,
    db: Session = Depends(get_db)
):
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    await LikeImgService.like_image(db, request.genImgId, user.id)
    return LikeResponse(
        code=0,
    )

@router.post("/cancel_like", response_model=CancelLikeResponse)
async def cancel_like(
    request: CancelLikeRequest,
    db: Session = Depends(get_db)
):
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    await LikeImgService.unlike_image(db, request.genImgId, user.id)
    return CancelLikeResponse(
        code=0,
    )

@router.post("/share", response_model=ShareResponse)
async def share(
    request: ShareRequest,
    db: Session = Depends(get_db)
):
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    await CommunityService.share_image(db, request.genImgId, user.id)
    return ShareResponse(
        code=0,
    )
