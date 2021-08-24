from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey
from models.database import Base
from datetime import date, datetime

def json_serial(obj):

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError (f'Type {obj} not serializable')

class User(Base):
    __tablename__ = 'users'
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.now(), nullable=False)
    updated_at = Column(DateTime, default=datetime.now(),
                        onupdate=datetime.now(), nullable=False)

    def __init__(self, name=None, email=None, hashed_password=None,
                 created_at=None, updated_at=None):
        self.name = name
        self.email = email
        self.hashed_password = hashed_password
        self.created_at = created_at
        self.updated_at = updated_at

    def __repr__(self):
        return "{}".format(self.email)


class Contact(Base):
    __tablename__ = 'contacts'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    is_2week = Column(Boolean, nullable=False)
    is_1month = Column(Boolean, nullable=False)
    started_at = Column(Date, nullable=False)

    def __init__(self, user_id=None, is_2week=None, is_1month=None,
                 started_at=None):
        self.user_id = user_id
        self.is_2week = is_2week
        self.is_1month = is_1month
        self.started_at = started_at

    def __repr__(self):
        return "{}".format(self.user_id)
