"""数据库引擎与会话。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import DB_URL

connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """建表（幂等）+ 轻量迁移。对应 sql/schema.sql。"""
    from . import models  # noqa: F401  确保模型已注册
    Base.metadata.create_all(bind=engine)   # 只新建缺失的表，不动已存在表的数据
    _migrate()


def _migrate():
    """为老库补新列（不丢数据）。SQLite 的 ALTER TABLE ADD COLUMN 是非破坏性的。"""
    add_cols = [("content_html", "TEXT"), ("wx_full", "INTEGER DEFAULT 0")]
    try:
        with engine.connect() as conn:
            if DB_URL.startswith("sqlite"):
                existing = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(posts)").fetchall()]
                for name, typ in add_cols:
                    if name not in existing:
                        conn.exec_driver_sql(f"ALTER TABLE posts ADD COLUMN {name} {typ}")
                conn.commit()
            else:
                for name, typ in add_cols:
                    try:
                        conn.exec_driver_sql(f"ALTER TABLE posts ADD COLUMN {name} {typ}")
                        conn.commit()
                    except Exception:
                        pass  # 列已存在等
    except Exception:
        pass
