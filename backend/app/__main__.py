from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.seed import seed_demo


def main() -> None:
    db: Session = SessionLocal()
    try:
        seed_demo(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
