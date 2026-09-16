from app.db.session import engine, Base
from app.db.models import (
    Member,
    Document,
    Page,
    PiiMapping,
    Job,
    Policy,
    PolicyParty,
    Coverage,
    Clause,
    Evidence,
    LLMCall,
    Reminder,
    AppSetting,
)


def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("""
            CREATE VIRTUAL TABLE IF NOT EXISTS clause_fts USING fts5(
                text_masked,
                title,
                content='clause',
                content_rowid='rowid',
                tokenize='trigram'
            );
        """)


if __name__ == "__main__":
    init_db()
    print("Database tables & FTS5 initialized successfully.")

