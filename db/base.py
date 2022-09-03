from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

engine = create_engine(
    "sqlite:///data/receipts.db",
    echo=True,
    encoding="utf-8",
)
Session = sessionmaker(bind=engine)

Base = declarative_base()
