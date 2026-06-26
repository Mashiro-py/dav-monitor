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
    content = Column(Text)
    publish_time = Column(DateTime, index=True)                # UTC
    collect_time = Column(DateTime, nullable=False)            # UTC
    original_url = Column(Text, nullable=False)
    platform_post_id = Column(Text)
    media_urls = Column(Text, default="[]")                    # JSON array
    stats = Column(Text, default="{}")                         # JSON object
    raw_json = Column(Text)                                     # JSON
    sentiment = Column(Text, index=True)                       # positive/negative/neutral/None
    keywords = Column(Text)                                     # JSON array / None
    dedup_key = Column(Text, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False)
