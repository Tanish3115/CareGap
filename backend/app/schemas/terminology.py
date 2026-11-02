from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500, pattern=r"^[^\x00]+$")
]


class TerminologyCoding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    system: Text
    code: Text
    display: Text
    release: Text
    evidence_reference: Text
    catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mode: Literal["synthetic", "approved_catalog"]
    checked: bool = False
    uncertain: bool = True


class CatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aliases: list[Text] = Field(min_length=1, max_length=50)
    system: Text
    code: Text
    display: Text
    evidence_reference: Text


class TerminologyCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference: Text
    release: Text
    entries: list[CatalogEntry] = Field(min_length=1, max_length=20000)
