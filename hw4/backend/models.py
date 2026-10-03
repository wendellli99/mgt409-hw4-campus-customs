"""Typed API contracts and deliberately small agent outputs."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Stock(BaseModel):
    size: str
    quantity: int = Field(ge=0)


class Product(BaseModel):
    product_id: str
    name: str
    garment_type: str
    description: str
    colors: list[str]
    search_tags: list[str]
    image_url: str
    price: float = Field(ge=0)
    inventory: list[Stock]
    total_stock: int = Field(ge=0)


class User(BaseModel):
    id: int
    first_name: str
    last_name: str
    name: str
    email: str


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator('first_name', 'last_name')
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError('Enter a valid name.')
        return value

    @field_validator('email')
    @classmethod
    def clean_email(cls, value: str) -> str:
        import re
        value = value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Enter a valid email address.')
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class PageContext(BaseModel):
    model_config = ConfigDict(extra='forbid')
    path: str = Field(default='/', max_length=300)
    product_id: str | None = Field(default=None, max_length=150)


class HistoryMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message: str = Field(min_length=1, max_length=2000)
    page_context: PageContext = Field(default_factory=PageContext)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=20)

    @field_validator('message')
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('Please type a message.')
        return value.strip()


class AgentReply(BaseModel):
    """The model chooses references; the server supplies authoritative product cards."""
    reply: str = Field(min_length=1, max_length=4000)
    product_ids: list[str] = Field(default_factory=list, max_length=12)


class Source(BaseModel):
    table: str
    product_ids: list[str]
    checked_at: str


class ChatResponse(BaseModel):
    reply: str
    products: list[Product]
    search_performed: bool
    run_id: str
    sources: list[Source]


class SearchResult(BaseModel):
    products: list[Product]
    total: int
    filters: dict
    result_cap: int
    message: str


class ProductLookup(BaseModel):
    found: bool
    product: Product | None = None
    color_interpretation: Literal['pictured_design_colors'] = 'pictured_design_colors'
    color_variants_recorded: Literal[False] = False
    message: str


class StockLookup(BaseModel):
    found: bool
    product_id: str
    name: str | None = None
    requested_size: str | None = None
    stock: list[Stock] = Field(default_factory=list)
    message: str
