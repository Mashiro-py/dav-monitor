"""posts 表 ORM 模型，与 docs/DATA_MODEL.md、sql/schema.sql 一一对应。"""
from sqlalchemy import Column, Integer, Text, DateTime

from .db import Base


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(Text, nullable=False, index=True)          # weibo / x / wechat
    account_name = Column(Text, nullable=False, index=True)
    author_name = Column(Text)
    author_url = Column(Text)
    title = Column(Text)
    content = Column(Text)                                      # 纯文本（列表预览/搜索）
    content_html = Column(Text)                                 # 富文本 HTML（详情图文展示）
    publish_time = Column(DateTime, index=True)                # UTC
    collect_time = Column(DateTime, nullable=False)            # UTC
    original_url = Column(Text, nullable=False)
    platform_post_id = Column(Text)
    media_urls = Column(Text, default="[]")                    # JSON array
    stats = Column(Text, default="{}")                         # JSON object
    raw_json = Column(Text)                                     # JSON
    sentiment = Column(Text, index=True)                       # positive/negative/neutral/None
    keywords = Column(Text)                                     # JSON array / None
    wx_full = Column(Integer, default=0, index=True)           # 公众号正文采集状态：0/NULL=待采 1=已补全文 2=已失效(删除/违规/仅客户端，不再采)
    dedup_key = Column(Text, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False)


class Analysis(Base):
    """AI 热点态势分析结果（DeepSeek）。新表由 create_all 自动创建，不影响 posts 老数据。
    只存成功的分析 → 当日 manual 行数即手动配额用量，失败天然不扣配额。"""
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, index=True)   # 完成时间 UTC
    trigger_type = Column(Text, nullable=False, index=True)    # auto / manual
    model = Column(Text)                                        # 实际使用的模型名
    range_start = Column(DateTime)                              # 分析窗口起点 UTC
    range_end = Column(DateTime)                                # 分析窗口终点 UTC
    covered_count = Column(Integer, default=0)                  # 实际送入模型的条数
    total_count = Column(Integer, default=0)                    # 窗口内总条数（>covered 说明截断）
    source_stats = Column(Text, default="{}")                   # JSON: {"weibo":45,"wechat":30,"x":12}
    result_json = Column(Text, nullable=False)                  # JSON: 双语结构化结果（summary/hot_events/key_opinions）
