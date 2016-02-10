from aldjemy.core import get_engine
from gargantext import settings


# get engine, session, etc.

from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

def get_engine():
    from sqlalchemy import create_engine
    url = 'postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}'.format(
        **settings.DATABASES['default']
    )
    return create_engine(url, use_native_hstore=True)

engine = get_engine()

Base = declarative_base()

Session = sessionmaker(bind=engine)


# tools to build models

from sqlalchemy.orm import aliased
from sqlalchemy.types import *
from sqlalchemy.schema import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
