import csv
import io
import logging
import re
from typing import List, Dict, Any, Optional
from fastapi import UploadFile
from sqlalchemy.orm import Session

from ..models.models import FashionData
from ..dto.csv_process import FashionDataItem, ProcessCsvResponseData, FrontendImageItem, ImageDetailItem, SimilarImageItem


logger = logging.getLogger(__name__)


class CsvProcessService:
    """CSV处理服务"""
    
    @staticmethod
    async def process_csv_file(
        db: Session,
        csv_file: UploadFile
    ) -> ProcessCsvResponseData:
        """
        处理CSV文件和图片上传
        
        Args:
            db: 数据库会话
            csv_file: CSV文件
            
        Returns:
            处理结果
        """
        try:
            # 解析CSV文件
            csv_data = await CsvProcessService._parse_csv_file(csv_file)
            logger.info(f"解析CSV文件完成，共{len(csv_data)}条记录")
            
            total_records = len(csv_data)
            processed_records = 0
            failed_records = 0
            processed_images = 0
            failed_images = 0
            error_details = []
            
            # 批量处理数据
            fashion_data_list = []
            
            for index, row in enumerate(csv_data):
                try:
                    # 创建FashionDataItem
                    fashion_item = await CsvProcessService._process_single_row(row, index)
                    
                    if fashion_item:
                        fashion_data_list.append(fashion_item)
                        processed_records += 1
                        logger.info(f"第{index+1}行数据处理成功: {fashion_item.record_id}")
                    else:
                        failed_records += 1
                        
                except Exception as e:
                    failed_records += 1
                    error_msg = f"第{index+1}行数据处理失败: {str(e)}"
                    error_details.append(error_msg)
                    logger.error(error_msg)
            
            # 批量保存到数据库
            if fashion_data_list:
                saved_count = await CsvProcessService._batch_save_to_db(db, fashion_data_list)
                logger.info(f"数据库保存完成，成功保存{saved_count}条记录")
            
            return ProcessCsvResponseData(
                total_records=total_records,
                processed_records=processed_records,
                failed_records=failed_records,
                processed_images=0,  # 不再处理图片上传
                failed_images=0,    # 不再处理图片上传
                error_details=error_details
            )
            
        except Exception as e:
            logger.error(f"处理CSV文件失败: {str(e)}")
            raise e
    
    @staticmethod
    async def _parse_csv_file(csv_file: UploadFile) -> List[Dict[str, str]]:
        """解析CSV文件"""
        try:
            # 读取CSV文件内容
            content = await csv_file.read()
            
            # 处理编码
            try:
                content_str = content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    content_str = content.decode('gbk')
                except UnicodeDecodeError:
                    content_str = content.decode('utf-8', errors='ignore')
            
            # 使用csv.DictReader解析
            csv_reader = csv.DictReader(io.StringIO(content_str))
            csv_data = []
            
            for row in csv_reader:
                # 清理字段名（去除BOM和空格）
                clean_row = {}
                for key, value in row.items():
                    if key:
                        clean_key = key.strip().replace('\ufeff', '')
                        clean_row[clean_key] = value.strip() if value else ""
                csv_data.append(clean_row)
            
            return csv_data
            
        except Exception as e:
            logger.error(f"解析CSV文件失败: {str(e)}")
            raise ValueError(f"CSV文件格式错误: {str(e)}")
    
    @staticmethod
    async def _process_single_row(row: Dict[str, str], index: int) -> Optional[FashionDataItem]:
        """处理单行数据"""
        try:
            # 检查必要字段
            required_fields = ['记录 ID', 'slug', 'gender', 'feature', 'clothing description', 'type']
            for field in required_fields:
                if field not in row or not row[field].strip():
                    logger.warning(f"第{index+1}行缺少必要字段: {field}")
                    return None
            
            return FashionDataItem(
                record_id=row.get('记录 ID', ''),
                slug=row.get('slug', ''),
                gender=row.get('gender', ''),
                feature=row.get('feature', ''),
                clothing_description=row.get('clothing description', ''),
                type=row.get('type', ''),
                complete_prompt=row.get('完整 prompt', ''),
                choose_img=row.get('选中图', ''),  # 保留原始图片地址
                image_url=row.get('选中图', '')   # 直接映射到image_url
            )
            
        except Exception as e:
            logger.error(f"处理第{index+1}行数据失败: {str(e)}")
            return None
    

    
    @staticmethod
    async def _batch_save_to_db(db: Session, fashion_data_list: List[FashionDataItem]) -> int:
        """批量保存到数据库"""
        try:
            saved_count = 0
            
            for item in fashion_data_list:
                # 检查是否已存在相同record_id的记录
                existing = db.query(FashionData).filter(
                    FashionData.record_id == item.record_id
                ).first()
                
                if existing:
                    # 更新现有记录
                    existing.slug = item.slug
                    existing.gender = item.gender
                    existing.feature = item.feature
                    existing.clothing_description = item.clothing_description
                    existing.type = item.type
                    existing.complete_prompt = item.complete_prompt
                    existing.choose_img = item.choose_img
                    existing.image_url = item.image_url
                    logger.info(f"更新现有记录: {item.record_id}")
                else:
                    # 创建新记录
                    new_fashion_data = FashionData(
                        record_id=item.record_id,
                        slug=item.slug,
                        gender=item.gender,
                        feature=item.feature,
                        clothing_description=item.clothing_description,
                        type=item.type,
                        complete_prompt=item.complete_prompt,
                        choose_img=item.choose_img,
                        image_url=item.image_url
                    )
                    db.add(new_fashion_data)
                    logger.info(f"创建新记录: {item.record_id}")
                
                saved_count += 1
            
            # 提交事务
            db.commit()
            logger.info(f"批量保存完成，共保存{saved_count}条记录")
            
            return saved_count
            
        except Exception as e:
            db.rollback()
            logger.error(f"批量保存到数据库失败: {str(e)}")
            raise e
    
    @staticmethod
    def get_fashion_data(
        db: Session,
        page: int = 1,
        page_size: int = 10,
        gender: Optional[str] = None,
        type_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取时尚数据"""
        try:
            # 构建查询
            query = db.query(FashionData)
            
            # 添加筛选条件
            if gender:
                query = query.filter(FashionData.gender == gender)
            if type_filter:
                query = query.filter(FashionData.type == type_filter)
            
            # 获取总数
            total = query.count()
            
            # 分页
            offset = (page - 1) * page_size
            items = query.offset(offset).limit(page_size).all()
            
            # 转换为DTO
            fashion_items = []
            for item in items:
                fashion_items.append(FashionDataItem(
                    record_id=item.record_id,
                    slug=item.slug,
                    gender=item.gender,
                    feature=item.feature,
                    clothing_description=item.clothing_description,
                    type=item.type,
                    complete_prompt=item.complete_prompt,
                    choose_img=item.choose_img,
                    image_url=item.image_url
                ))
            
            return {
                "total": total,
                "list": fashion_items
            }
            
        except Exception as e:
            logger.error(f"获取时尚数据失败: {str(e)}")
            raise e
    
    @staticmethod
    def get_frontend_images(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        type_filter: Optional[List[str]] = None,
        gender_filter: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """获取前端图片列表（专门用于前端展示）"""
        try:
            from sqlalchemy import case
            
            # 构建查询 - 只返回有图片的记录
            query = db.query(FashionData).filter(
                FashionData.image_url.isnot(None),
                FashionData.image_url != ""
            )
            
            # 添加类型筛选
            if type_filter:
                query = query.filter(FashionData.type.in_(type_filter))
            
            # 添加性别筛选
            if gender_filter:
                query = query.filter(FashionData.gender.in_(gender_filter))
            
            # 自定义排序逻辑：
            # 1. 性别优先级：Female = 0, Male = 1 (女性优先)
            # 2. 类型优先级：Evening Wear = 0, Casual = 1, Professional = 2, Sportswear = 3, Kidswear = 4
            # 3. 时间倒序：最新的在前
            
            gender_priority = case(
                (FashionData.gender == 'Female', 0),
                (FashionData.gender == 'Male', 1),
                else_=2
            )
            
            type_priority = case(
                (FashionData.type == 'Evening Wear', 0),
                (FashionData.type == 'Casual', 1),
                (FashionData.type == 'Professional', 2),
                (FashionData.type == 'Sportswear', 3),
                (FashionData.type == 'Kidswear', 4),
                else_=5
            )
            
            # 应用排序：性别优先 -> 类型优先 -> 时间倒序
            query = query.order_by(
                gender_priority.asc(),      # 性别优先（Female = 0 排前面）
                type_priority.asc(),        # 类型优先（Evening Wear = 0 排前面）
                FashionData.create_time.desc()  # 时间倒序（最新的在前）
            )
            
            # 获取总数
            total = query.count()
            
            # 分页
            offset = (page - 1) * page_size
            items = query.offset(offset).limit(page_size).all()
            
            # 计算是否还有更多数据
            has_more = (offset + len(items)) < total
            
            # 转换为前端DTO
            frontend_items = []
            for item in items:
                frontend_items.append(FrontendImageItem(
                    id=item.id,
                    record_id=item.record_id,
                    slug=item.slug,
                    image_url=item.image_url,
                    clothing_description=item.clothing_description,
                    complete_prompt=item.complete_prompt,
                    type=item.type,
                    gender=item.gender,
                    feature=item.feature,
                    create_time=item.create_time.strftime('%Y-%m-%d %H:%M:%S') if item.create_time else ""
                ))
            
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "has_more": has_more,
                "list": frontend_items
            }
            
        except Exception as e:
            logger.error(f"获取前端图片列表失败: {str(e)}")
            raise e
    
    @staticmethod
    def get_image_detail(
        db: Session,
        slug: Optional[str] = None,
        record_id: Optional[str] = None
    ) -> Optional[ImageDetailItem]:
        """获取图片详情（通过slug或record_id）"""
        try:
            # 必须提供至少一个查询参数
            if not slug and not record_id:
                raise ValueError("必须提供slug或record_id参数")
            
            # 构建查询
            query = db.query(FashionData)
            
            # 优先使用slug查询，其次使用record_id
            if slug:
                item = query.filter(FashionData.slug == slug).first()
                logger.info(f"通过slug查询图片详情: {slug}")
            else:
                item = query.filter(FashionData.record_id == record_id).first()
                logger.info(f"通过record_id查询图片详情: {record_id}")
            
            # 检查是否找到记录
            if not item:
                identifier = slug if slug else record_id
                identifier_type = "slug" if slug else "record_id"
                logger.warning(f"未找到图片详情: {identifier_type}={identifier}")
                return None
            
            # 转换为详情DTO
            detail_item = ImageDetailItem(
                id=item.id,
                record_id=item.record_id,
                slug=item.slug,
                image_url=item.image_url,
                choose_img=item.choose_img,
                clothing_description=item.clothing_description,
                complete_prompt=item.complete_prompt,
                type=item.type,
                gender=item.gender,
                feature=item.feature,
                create_time=item.create_time.strftime('%Y-%m-%d %H:%M:%S') if item.create_time else "",
                update_time=item.update_time.strftime('%Y-%m-%d %H:%M:%S') if item.update_time else ""
            )
            
            # 获取相似图片
            similar_images = CsvProcessService._find_similar_images(db, item, limit=5)
            
            # 更新详情项，添加相似图片
            detail_item.similar_images = similar_images
            
            logger.info(f"图片详情查询成功: id={item.id}, slug={item.slug}, record_id={item.record_id}, 相似图片数量: {len(similar_images)}")
            return detail_item
            
        except Exception as e:
            logger.error(f"获取图片详情失败: {str(e)}")
            raise e
    
    @staticmethod
    def _preprocess_text(text: str) -> str:
        """预处理文本：转换为小写，去除标点符号"""
        if not text:
            return ""
        # 转换为小写，去除标点符号，只保留字母、数字和空格
        return re.sub(r'[^\w\s]', '', text.lower())
    
    @staticmethod
    def _calculate_word_overlap_similarity(text1: str, text2: str) -> float:
        """计算两个文本的词汇重叠相似度"""
        if not text1 or not text2:
            return 0.0
        
        # 预处理文本
        processed_text1 = CsvProcessService._preprocess_text(text1)
        processed_text2 = CsvProcessService._preprocess_text(text2)
        
        # 分割成词汇集合
        words1 = set(processed_text1.split())
        words2 = set(processed_text2.split())
        
        # 如果任一集合为空，返回0
        if not words1 or not words2:
            return 0.0
        
        # 计算交集和并集
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        # 返回Jaccard相似度
        return len(intersection) / len(union) if union else 0.0
    
    @staticmethod
    def _find_similar_images(db: Session, current_image: FashionData, limit: int = 5) -> List[SimilarImageItem]:
        """查找相似图片"""
        try:
            # 1. 按标签筛选候选图片（相同type, gender, feature）
            candidates = db.query(FashionData).filter(
                FashionData.type == current_image.type,
                FashionData.gender == current_image.gender,
                FashionData.feature == current_image.feature,
                FashionData.id != current_image.id  # 排除自己
            ).all()
            
            if not candidates:
                logger.info(f"未找到相同标签的候选图片: type={current_image.type}, gender={current_image.gender}, feature={current_image.feature}")
                return []
            
            logger.info(f"找到{len(candidates)}张候选图片")
            
            # 2. 计算相似度
            similarities = []
            for candidate in candidates:
                similarity_score = CsvProcessService._calculate_word_overlap_similarity(
                    current_image.clothing_description,
                    candidate.clothing_description
                )
                similarities.append((candidate, similarity_score))
            
            # 3. 按相似度降序排序，取前limit张
            similarities.sort(key=lambda x: x[1], reverse=True)
            top_similarities = similarities[:limit]
            
            # 4. 转换为SimilarImageItem列表
            similar_images = []
            for candidate, score in top_similarities:
                similar_image = SimilarImageItem(
                    id=candidate.id,
                    record_id=candidate.record_id,
                    slug=candidate.slug,
                    image_url=candidate.image_url,
                    clothing_description=candidate.clothing_description,
                    type=candidate.type,
                    gender=candidate.gender,
                    feature=candidate.feature,
                    similarity_score=round(score, 4)  # 保留4位小数
                )
                similar_images.append(similar_image)
            
            logger.info(f"成功找到{len(similar_images)}张相似图片，最高相似度: {top_similarities[0][1] if top_similarities else 0}")
            return similar_images
            
        except Exception as e:
            logger.error(f"查找相似图片失败: {str(e)}")
            return []
