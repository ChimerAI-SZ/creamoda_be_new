from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, String, TIMESTAMP, Text, text
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, declarative_base, mapped_column
from sqlalchemy.orm.base import Mapped

Base = declarative_base()


class CollectImg(Base):
    __tablename__ = 'collect_img'
    __table_args__ = {'comment': '收藏图片表'}

    id = mapped_column(BigInteger, primary_key=True)
    gen_img_id = mapped_column(BigInteger, nullable=False, comment='生成图片id')
    user_id = mapped_column(BigInteger, nullable=False, comment='用户id')
    create_time = mapped_column(DateTime)


class Constant(Base):
    __tablename__ = 'constant'
    __table_args__ = (
        Index('idx_type', 'type'),
    )

    id = mapped_column(BigInteger, primary_key=True)
    type = mapped_column(Integer, comment='常量类型')
    code = mapped_column(String(100), comment='常量code')
    name = mapped_column(String(100), comment='常量value')
    create_time = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))


class ContactRecord(Base):
    __tablename__ = 'contact_record'
    __table_args__ = (
        Index('idx_gen_id', 'gen_id'),
        Index('idx_img_id', 'img_id'),
        Index('idx_uid', 'uid')
    )

    id = mapped_column(BigInteger, primary_key=True)
    gen_id = mapped_column(BigInteger)
    img_id = mapped_column(BigInteger)
    uid = mapped_column(BigInteger)
    source = mapped_column(String(100), comment='联系场景')
    contact_email = mapped_column(String(100), comment='联系邮箱')
    create_time = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))


class GenImgRecord(Base):
    __tablename__ = 'gen_img_record'
    __table_args__ = (
        Index('indx_uid', 'uid'),
    )

    id = mapped_column(BigInteger, primary_key=True)
    uid = mapped_column(BigInteger, nullable=False)
    type = mapped_column(Integer, comment='生图类型 1-文生图 2-图生图')
    format = mapped_column(String(20), comment='图片比例')
    width = mapped_column(Integer, comment='宽度')
    height = mapped_column(Integer, comment='高度')
    original_pic_url = mapped_column(Text)
    original_prompt = mapped_column(Text)
    refer_pic_url = mapped_column(Text, comment='参考图片链接')
    clothing_photo = mapped_column(Text, comment='衣服图片链接')
    cloth_type = mapped_column(String(50), comment='衣服类型')
    hex_color = mapped_column(String(50), comment='颜色')
    variation_type = mapped_column(Integer, comment='变化类型')
    status = mapped_column(TINYINT, comment='1-待生成 2-生成中 3-已生成 4-失败')
    with_human_model = mapped_column(TINYINT)
    gender = mapped_column(TINYINT)
    age = mapped_column(Integer)
    country = mapped_column(String(50))
    model_size = mapped_column(Integer)
    fidelity = mapped_column(Integer, comment='保真度（乘以100）')
    create_time = mapped_column(TIMESTAMP)
    update_time = mapped_column(TIMESTAMP)


class GenImgResult(Base):
    __tablename__ = 'gen_img_result'
    __table_args__ = (
        Index('idx_gen_id', 'gen_id'),
        Index('idx_uid', 'uid')
    )

    id = mapped_column(BigInteger, primary_key=True)
    gen_id = mapped_column(BigInteger, nullable=False)
    uid = mapped_column(BigInteger, nullable=False)
    style = mapped_column(String(50))
    prompt = mapped_column(Text, comment='提示词')
    status = mapped_column(TINYINT, comment='1-待生成 2-生成中 3-已生成')
    result_pic = mapped_column(Text, comment='生成结果图片')
    fail_count = mapped_column(Integer, server_default=text("'0'"), comment='失败次数')
    create_time = mapped_column(TIMESTAMP)
    update_time = mapped_column(TIMESTAMP)


class UploadRecord(Base):
    __tablename__ = 'upload_record'
    __table_args__ = (
        Index('idx_uid', 'uid'),
    )

    id = mapped_column(BigInteger, primary_key=True)
    pic_url = mapped_column(Text, nullable=False, comment='oss图片链接')
    uid = mapped_column(BigInteger, comment='上传人uid')
    origin_pic_url = mapped_column(Text, comment='原始图片链接（仅外部链接的情况记录）')
    create_time = mapped_column(TIMESTAMP)


class UserInfo(Base):
    __tablename__ = 'user_info'
    __table_args__ = (
        Index('idx_email', 'email', unique=True),
        Index('idx_google_sub_id', 'google_sub_id'),
        Index('idx_uid', 'uid', unique=True)
    )

    id = mapped_column(BigInteger, primary_key=True)
    email = mapped_column(String(200), nullable=False)
    status = mapped_column(TINYINT, nullable=False, server_default=text("'1'"), comment='用户状态 1-正常 2-禁用')
    email_verified = mapped_column(TINYINT, nullable=False, server_default=text("'2'"), comment='邮箱是否验证 1-是 2-否')
    uid = mapped_column(BigInteger, comment='用户id')
    username = mapped_column(String(100))
    pwd = mapped_column(String(200))
    salt = mapped_column(String(100))
    head_pic = mapped_column(String(200))
    google_sub_id = mapped_column(String(200), comment='google 用户唯一标识')
    google_access_token = mapped_column(String(500), comment='google access token')
    google_refresh_token = mapped_column(String(500))
    last_login_time = mapped_column(TIMESTAMP)
    create_time = mapped_column(TIMESTAMP)
    update_time = mapped_column(TIMESTAMP)
