from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, JSON, String, TIMESTAMP, Text, text
from sqlalchemy.dialects.mysql import TEXT, TINYINT
from sqlalchemy.orm import Mapped, declarative_base, mapped_column
from sqlalchemy.orm.base import Mapped

Base = declarative_base()


class BillingHistory(Base):
    __tablename__ = 'billing_history'
    __table_args__ = (
        Index('billing_history_uid_index', 'uid'),
        {'comment': '账单记录表'}
    )

    id = mapped_column(BigInteger, primary_key=True)
    uid = mapped_column(BigInteger)
    type = mapped_column(Integer, comment='订单类型 101-普通会员订阅 102-专业会员订阅 103-企业会员订阅 201-40积分购买 202-100积分购买 203-200积分购买')
    order_id = mapped_column(String(200), comment='订单id')
    sub_order_id = mapped_column(String(100), comment='副订单id，月度扣款存在')
    description = mapped_column(String(100), comment='描述')
    status = mapped_column(Integer, comment='状态 1-支付成功 2-支付失败 3-创建订单 4-已捕获')
    amount = mapped_column(Integer)
    create_time = mapped_column(DateTime)


class CollectImg(Base):
    __tablename__ = 'collect_img'
    __table_args__ = {'comment': '收藏图片表'}

    id = mapped_column(BigInteger, primary_key=True)
    gen_img_id = mapped_column(BigInteger, nullable=False, comment='生成图片id')
    user_id = mapped_column(BigInteger, nullable=False, comment='用户id')
    create_time = mapped_column(DateTime)


class CommunityImg(Base):
    __tablename__ = 'community_img'
    __table_args__ = (
        Index('community_img_uploader_index', 'uploader'),
        {'comment': '社区图库'}
    )

    id = mapped_column(BigInteger, primary_key=True)
    uploader = mapped_column(BigInteger, nullable=False, comment='上传者uid')
    gen_img_id = mapped_column(BigInteger, comment='生图结果id')
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
    description = mapped_column(String(50), comment='描述')
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


class Credit(Base):
    __tablename__ = 'credit'
    __table_args__ = (
        Index('credit_uid_uindex', 'uid', unique=True),
        {'comment': '积分表'}
    )

    id = mapped_column(BigInteger, primary_key=True)
    uid = mapped_column(BigInteger, nullable=False, comment='用户id')
    credit = mapped_column(Integer, comment='积分值')
    lock_credit = mapped_column(Integer, comment='锁定积分值')
    create_time = mapped_column(DateTime)
    update_time = mapped_column(DateTime)


class CreditHistory(Base):
    __tablename__ = 'credit_history'
    __table_args__ = (
        Index('credit_history_uid_index', 'uid'),
        {'comment': '积分历史'}
    )

    id = mapped_column(BigInteger, primary_key=True)
    uid = mapped_column(BigInteger, nullable=False)
    credit_change = mapped_column(Integer, comment='信用变化')
    source = mapped_column(String(200), comment='变化来源')
    create_time = mapped_column(DateTime)


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
    fabric_pic_url = mapped_column(TEXT, comment='面料图片链接')
    mask_pic_url = mapped_column(TEXT, comment='mask图片链接')
    cloth_type = mapped_column(String(50), comment='衣服类型')
    hex_color = mapped_column(String(50), comment='颜色')
    input_param_json = mapped_column(JSON, comment='输入参数')
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
        Index('gen_img_result_seo_img_uid_index', 'seo_img_uid'),
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
    seo_img_uid = mapped_column(String(500), comment='seo图片唯一id')
    description = mapped_column(Text, comment='图片描述')
    create_time = mapped_column(TIMESTAMP)
    update_time = mapped_column(TIMESTAMP)


class ImgMaterialTags(Base):
    __tablename__ = 'img_material_tags'
    __table_args__ = (
        Index('img_material_tags_gen_img_id_material_id_index', 'gen_img_id', 'material_id'),
        {'comment': '图片材质关联表'}
    )

    id = mapped_column(BigInteger, primary_key=True)
    gen_img_id = mapped_column(BigInteger, nullable=False)
    material_id = mapped_column(BigInteger, comment='材质id')


class ImgStyleTags(Base):
    __tablename__ = 'img_style_tags'
    __table_args__ = (
        Index('img_style_tags_gen_img_id_index', 'gen_img_id'),
        Index('img_style_tags_style_id_index', 'style_id'),
        {'comment': '图片风格关联表'}
    )

    id = mapped_column(BigInteger, primary_key=True)
    gen_img_id = mapped_column(BigInteger, nullable=False, comment='图片结果id')
    style_id = mapped_column(BigInteger, comment='风格id')


class LikeImg(Base):
    __tablename__ = 'like_img'
    __table_args__ = (
        Index('like_img_gen_img_id_index', 'gen_img_id'),
        Index('like_img_uid_index', 'uid'),
        {'comment': '图片点赞表'}
    )

    id = mapped_column(BigInteger, primary_key=True)
    gen_img_id = mapped_column(BigInteger, nullable=False, comment='图片id')
    uid = mapped_column(BigInteger, comment='用户id')
    create_time = mapped_column(DateTime)


class Material(Base):
    __tablename__ = 'material'
    __table_args__ = (
        Index('material_name_index', 'name'),
        {'comment': '材质表'}
    )

    id = mapped_column(BigInteger, primary_key=True)
    name = mapped_column(String(100))


class Subscribe(Base):
    __tablename__ = 'subscribe'
    __table_args__ = (
        Index('subscribe_uid_index', 'uid'),
        {'comment': '订阅表'}
    )

    id = mapped_column(BigInteger, primary_key=True)
    uid = mapped_column(BigInteger, nullable=False)
    paypal_sub_id = mapped_column(String(100), comment='paypal订阅id')
    level = mapped_column(Integer, comment='订阅等级 0-无 1-基础班 2-专业版 3-企业版')
    is_renew = mapped_column(Integer, comment='是否续订 1-是 0-否')
    sub_start_time = mapped_column(DateTime, comment='开始订阅时间')
    sub_end_time = mapped_column(DateTime, comment='结束订阅时间')
    renew_time = mapped_column(DateTime, comment='续订时间')
    billing_email = mapped_column(String(200), comment='订阅邮箱')
    cancel_time = mapped_column(DateTime, comment='取消订阅时间')
    create_time = mapped_column(DateTime)
    update_time = mapped_column(DateTime)


class SubscribeHistory(Base):
    __tablename__ = 'subscribe_history'
    __table_args__ = (
        Index('subscribe_history_uid_index', 'uid'),
        {'comment': '订阅历史'}
    )

    id = mapped_column(BigInteger, primary_key=True)
    uid = mapped_column(BigInteger, nullable=False)
    level = mapped_column(Integer, comment='订阅等级 0-无 1-基础 2-专业 3-企业')
    action = mapped_column(Integer, comment='动作 1-订阅 2-取消订阅')
    create_time = mapped_column(DateTime)


class TrendStyle(Base):
    __tablename__ = 'trend_style'
    __table_args__ = (
        Index('trend_style_name_index', 'name'),
        {'comment': '趋势风格'}
    )

    id = mapped_column(BigInteger, primary_key=True)
    name = mapped_column(String(100))


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


class FashionData(Base):
    __tablename__ = 'fashion_data'
    __table_args__ = (
        Index('idx_record_id', 'record_id'),
        Index('idx_slug', 'slug'),
        {'comment': '时尚数据表'}
    )

    id = mapped_column(BigInteger, primary_key=True)
    record_id = mapped_column(String(100), comment='记录ID')
    slug = mapped_column(String(200), comment='URL友好标识')
    gender = mapped_column(String(50), comment='性别')
    feature = mapped_column(String(100), comment='特征')
    clothing_description = mapped_column(Text, comment='服装描述')
    type = mapped_column(String(100), comment='类型')
    complete_prompt = mapped_column(Text, comment='完整prompt')
    image_url = mapped_column(Text, comment='OSS图片地址')
    choose_img = mapped_column(Text, comment='选中图片地址')
    create_time = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    update_time = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))


class UserInfo(Base):
    __tablename__ = 'user_info'
    __table_args__ = (
        Index('idx_email', 'email', unique=True),
        Index('idx_google_sub_id', 'google_sub_id')
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
