from sqlalchemy import Column, Integer, String, Float, Text
from pgvector.sqlalchemy import Vector
from database import Base

class Game(Base):
    __tablename__ = "games"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    genres = Column(String)
    description = Column(Text)
    mania_score = Column(Float)
    story_depth = Column(Float)
    gem_potential = Column(Float)
    embedding = Column(Vector(384)) # 💡 384차원 밀집 벡터 저장용