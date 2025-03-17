from sqlalchemy import Column, Index, String, TIMESTAMP, Text, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, TINYINT
from sqlalchemy.orm import Mapped, declarative_base, mapped_column
from sqlalchemy.orm.base import Mapped

Base = declarative_base()


class Constant(Base):
    __tablename__ = 'constant'
    __table_args__ = (
        Index('idx_type', 'type'),
    )

    id = mapped_column(BIGINT(20), primary_key=True)
    type = mapped_column(INTEGER(11), comment='常量类型')
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

    id = mapped_column(BIGINT(20), primary_key=True)
    gen_id = mapped_column(BIGINT(20))
    img_id = mapped_column(BIGINT(20))
    uid = mapped_column(BIGINT(20))
    source = mapped_column(String(100), comment='联系场景')
    contact_email = mapped_column(String(100), comment='联系邮箱')
    create_time = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))


class GenImgRecord(Base):
    __tablename__ = 'gen_img_record'
    __table_args__ = (
        Index('indx_uid', 'uid'),
    )

    id = mapped_column(BIGINT(20), primary_key=True)
    uid = mapped_column(BIGINT(20), nullable=False)
    type = mapped_column(INTEGER(11), comment='生图类型 1-文生图 2-图生图')
    original_pic_url = mapped_column(Text)
    original_prompt = mapped_column(Text)
    variation_type = mapped_column(INTEGER(11), comment='变化类型')
    status = mapped_column(TINYINT(4), comment='1-待生成 2-生成中 3-已生成')
    with_human_model = mapped_column(TINYINT(4))
    gender = mapped_column(TINYINT(4))
    age = mapped_column(INTEGER(11))
    country = mapped_column(String(50))
    model_size = mapped_column(INTEGER(11))
    fidelity = mapped_column(INTEGER(11), comment='保真度（乘以100）')
    create_time = mapped_column(TIMESTAMP)
    update_time = mapped_column(TIMESTAMP)


class GenImgResult(Base):
    __tablename__ = 'gen_img_result'
    __table_args__ = (
        Index('idx_gen_id', 'gen_id'),
        Index('idx_uid', 'uid')
    )

    id = mapped_column(BIGINT(20), primary_key=True)
    gen_id = mapped_column(BIGINT(20), nullable=False)
    uid = mapped_column(BIGINT(20), nullable=False)
    style = mapped_column(String(50))
    prompt = mapped_column(Text)
    status = mapped_column(TINYINT(4), comment='1-待生成 2-生成中 3-已生成')
    result_pic = mapped_column(Text, comment='生成结果图片')
    fail_count = mapped_column(INTEGER(11), server_default=text("'0'"), comment='失败次数')
    create_time = mapped_column(TIMESTAMP)
    update_time = mapped_column(TIMESTAMP)


class UploadRecord(Base):
    __tablename__ = 'upload_record'
    __table_args__ = (
        Index('idx_uid', 'uid'),
    )

    id = mapped_column(BIGINT(20), primary_key=True)
    pic_url = mapped_column(Text, nullable=False)
    uid = mapped_column(BIGINT(20))
    create_time = mapped_column(TIMESTAMP)


class UserInfo(Base):
    __tablename__ = 'user_info'
    __table_args__ = (
        Index('idx_email', 'email', unique=True),
        Index('idx_google_sub_id', 'google_sub_id'),
        Index('idx_uid', 'uid', unique=True),
        Index('idx_username', 'username', unique=True)
    )

    id = mapped_column(BIGINT(20), primary_key=True)
    email = mapped_column(String(200), nullable=False)
    status = mapped_column(TINYINT(4), nullable=False, server_default=text("'1'"), comment='用户状态 1-正常 2-禁用')
    email_verified = mapped_column(TINYINT(4), nullable=False, server_default=text("'2'"), comment='邮箱是否验证 1-是 2-否')
    uid = mapped_column(BIGINT(20), comment='用户id')
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
