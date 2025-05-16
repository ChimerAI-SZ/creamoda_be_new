from multiprocessing import AuthenticationError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from src.core.context import get_current_user_context
from src.db.session import get_db
from src.dto.collect import CollectListData, CollectListItem, CollectListResponse, CollectRequest, CollectResponse
from src.models.models import GenImgResult, CollectImg


router = APIRouter()

@router.post("/ops", response_model=CollectResponse)
async def collect(
    request: CollectRequest,
    db: Session = Depends(get_db)
):
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    # 1. 查询gen_img_result表中是否存在对应记录
    gen_img = db.query(GenImgResult).filter(GenImgResult.id == request.genImgId).first()
    if not gen_img:
        raise HTTPException(status_code=404, detail="生成图片记录不存在")
    
    # 2. 校验是否为用户自己的图片
    if gen_img.uid != user.id:
        raise HTTPException(status_code=403, detail="无权操作该图片")
    
    # 3. 查询collect_img表中是否已经存在/不存在记录
    collect_record = db.query(CollectImg).filter(
        CollectImg.gen_img_id == request.genImgId,
        CollectImg.user_id == user.id
    ).first()
    
    # 4. 新增/删除collect_img记录
    if request.action == 1:  # 收藏
        if not collect_record:  # 如果记录不存在，则创建
            collect_record = CollectImg(
                gen_img_id=request.genImgId,
                user_id=user.id,
                create_time=datetime.now()
            )
            db.add(collect_record)
            db.commit()
            return CollectResponse(code=200, msg="收藏成功")
        else:
            return CollectResponse(code=200, msg="已经收藏过了")
    
    elif request.action == 2:  # 取消收藏
        if collect_record:  # 如果记录存在，则删除
            db.delete(collect_record)
            db.commit()
            return CollectResponse(code=200, msg="取消收藏成功")
        else:
            return CollectResponse(code=200, msg="未收藏过该图片")
    
    else:
        raise HTTPException(status_code=400, detail="无效的action参数")
    
@router.get("/list", response_model=CollectListResponse)
async def collect_list(
    page: int = 1,
    pageSize: int = 10,
    db: Session = Depends(get_db)
):
    # 获取当前用户信息
    user = get_current_user_context()
    if not user:
        raise AuthenticationError()
    
    # 计算分页参数
    skip = (page - 1) * pageSize
    limit = pageSize
    
    # 1. 根据用户id分页查询collect_img表中的信息，按时间倒排
    query = db.query(
        CollectImg.gen_img_id,
        GenImgResult.result_pic,
        CollectImg.create_time
    ).join(
        GenImgResult, 
        CollectImg.gen_img_id == GenImgResult.id
    ).filter(
        CollectImg.user_id == user.id
    ).order_by(
        CollectImg.create_time.desc()
    )
    
    # 获取总记录数
    total = query.count()
    
    # 应用分页
    results = query.offset(skip).limit(limit).all()
    
    # 2. 构建响应数据
    collect_items = []
    for item in results:
        # 格式化时间为字符串
        create_time = item.create_time.strftime("%Y-%m-%d %H:%M:%S") if item.create_time else ""
        
        collect_items.append(CollectListItem(
            genImgId=item.gen_img_id,
            resultPic=item.result_pic or "",
            createTime=create_time
        ))
    
    # 构建分页数据
    data = CollectListData(
        list=collect_items,
        total=total
    )
    
    return CollectListResponse(code=200, msg="success", data=data)
    
    