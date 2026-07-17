from sqlalchemy import Engine, create_engine

from .config import load_db_config


def get_engine() -> Engine:
    config = load_db_config()
    return create_engine(config.sqlalchemy_url)
