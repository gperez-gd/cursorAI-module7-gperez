import re

from app import db


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)

    posts = db.relationship("Post", back_populates="category", lazy="dynamic")

    def __init__(self, name: str, slug: str | None = None):
        self.name = name
        self.slug = slug or _slugify(name)

    def __repr__(self) -> str:
        return f"<Category {self.name}>"
