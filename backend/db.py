from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from . import config

engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True)
    folder = Column(String, nullable=False)
    repo_name = Column(String, nullable=False)
    description = Column(String, default="")
    visibility = Column(String, default="private")
    status = Column(String, default="CREATED")
    commits = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    github_url = Column(String, nullable=True)
    error = Column(Text, nullable=True)
    plan_json = Column(Text, nullable=True)  # plan contains no secret values


Base.metadata.create_all(engine)
