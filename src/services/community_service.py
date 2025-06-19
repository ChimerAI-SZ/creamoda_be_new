
from datetime import datetime
from requests import Session
from sqlalchemy import and_

from src.constants.gen_img_type import GenImgType
from src.dto.community import CommunityDetailResponseData, CommunityListData, CommunityListItem, Creator
from src.exceptions.base import CustomException
from src.models.models import CollectImg, CommunityImg, GenImgRecord, GenImgResult, ImgMaterialTags, ImgStyleTags, LikeImg, Material, TrendStyle, UserInfo
from src.services.like_img_service import LikeImgService


class CommunityService:

    @staticmethod
    async def query_community_list(db: Session, uid: int, page: int, pageSize: int):

        query = db.query(CommunityImg, GenImgResult, CollectImg, LikeImg, UserInfo).join(
            GenImgResult, CommunityImg.gen_img_id == GenImgResult.id
        ).outerjoin(
            CollectImg, 
            and_(
                CollectImg.gen_img_id == GenImgResult.id,
                CollectImg.user_id == uid
        )
        ).outerjoin(
            LikeImg, 
            and_(
                LikeImg.gen_img_id == GenImgResult.id,
                LikeImg.uid == uid
            )
        ).join(
            UserInfo, CommunityImg.uploader == UserInfo.id
        ).filter(GenImgResult.id is not None, UserInfo.id is not None).order_by(CommunityImg.id.desc())
        
        # 计算总记录数
        total_count = query.count()

        paginated_results = query.order_by(GenImgResult.id.desc())\
            .offset((page - 1) * pageSize)\
            .limit(pageSize)\
            .all()
        
        result_list = []
        for community_img, gen_img_result, collect_img, like_img, user_info in paginated_results:
            like_count = await LikeImgService.get_like_count(db, gen_img_result.id)
            item = CommunityListItem(
                genImgId=gen_img_result.id,
                picUrl=gen_img_result.result_pic,
                isCollected=1 if collect_img else 0,
                seoImgUid=gen_img_result.seo_img_uid,
                creator=Creator(
                    uid=user_info.id,
                    name=user_info.username,
                    email=user_info.email
                ),
                islike=1 if like_img else 0,
                likeCount=like_count,
            )

            result_list.append(item)
        
        return CommunityListData(
            total=total_count,
            list=result_list
        )
    
    
    @staticmethod
    async def query_community_detail(db: Session, seoImgUid: str, uid: int):
        imgResult, communityImg, genImgRecord, userInfo = db.query(GenImgResult, CommunityImg, GenImgRecord, UserInfo).join(
            CommunityImg, CommunityImg.gen_img_id == GenImgResult.id
        ).join(
            GenImgRecord, GenImgRecord.id == GenImgResult.gen_id
        ).join(
            UserInfo, CommunityImg.uploader == UserInfo.id
        ).filter(GenImgResult.id is not None, 
                 CommunityImg.id is not None,
                 GenImgRecord.id is not None,
                 UserInfo.id is not None, 
                 GenImgResult.seo_img_uid == seoImgUid).first()

        material_query = db.query(Material, ImgMaterialTags).join(
            ImgMaterialTags, Material.id == ImgMaterialTags.material_id
        ).filter(ImgMaterialTags.gen_img_id == imgResult.id).all()

        materials_list = []
        for material, img_material_tags in material_query:
            materials_list.append(material.name)

        trend_query = db.query(TrendStyle, ImgStyleTags).join(
            ImgStyleTags, TrendStyle.id == ImgStyleTags.style_id
        ).filter(ImgStyleTags.gen_img_id == imgResult.id).all()

        trend_styles_list = []
        for trend_style, img_style_tags in trend_query:
            trend_styles_list.append(trend_style.name)
            
        like_count = await LikeImgService.get_like_count(db, imgResult.id)

        if uid:
            likeImg = await LikeImgService.get_user_like_status(db, imgResult.id, uid)
            collectImg = db.query(CollectImg).filter(CollectImg.gen_img_id == imgResult.id, CollectImg.user_id == uid).first()
        else:
            likeImg = False
            collectImg = None

        gen_type = GenImgType.get_by_type_and_variation_type(genImgRecord.type, genImgRecord.variation_type)

        result = CommunityDetailResponseData(
            genImgId=imgResult.id,
            genType=gen_type.path.split(",") if gen_type.path else None,
            prompt=genImgRecord.original_prompt,
            originalImgUrl=imgResult.result_pic,
            materials=materials_list,
            trendStyles=trend_styles_list,
            description=imgResult.description,
            isLike=1 if likeImg else 0,
            likeCount=like_count,
            isCollected=1 if collectImg else 0,
            creator=Creator(
                    uid=userInfo.id,
                    name=userInfo.username,
                    email=userInfo.email
                ),
        )

        return result
    
    @staticmethod
    async def share_image(db: Session, genImgId: int, uid: int):
        # 1. 查询图片
        imgResult = db.query(GenImgResult).filter(GenImgResult.id == genImgId).first()
        if not imgResult:
            raise CustomException(code=400, message="picture not found")
        if imgResult.uid != uid:
            raise CustomException(code=400, message="picture not belong to current user")
        if not imgResult.seo_img_uid:
            raise CustomException(code=400, message="picture cant share")
        
        # 2. 查询社区是否已存在
        communityImg = db.query(CommunityImg).filter(CommunityImg.gen_img_id == genImgId).first()
        if communityImg:
            raise CustomException(code=400, message="picture already shared")
        
        # 3. 创建社区图片
        communityImg = CommunityImg(
            gen_img_id=genImgId,
            uploader=uid,
            create_time=datetime.now(),
        )

        db.add(communityImg)
        db.commit()
        db.refresh(communityImg)

        return communityImg
