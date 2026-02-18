from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from uuid import UUID


# --- Base Entity Models ---
class VendorBase(BaseModel):
    canonical_name: str
    duns: Optional[str] = None
    uei: Optional[str] = None
    resolved_by_llm: bool = False
    resolution_confidence: Optional[float] = None


class Vendor(VendorBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    updated_at: datetime


class AgencyBase(BaseModel):
    agency_code: str
    agency_name: str


class Agency(AgencyBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    updated_at: datetime


class ContractBase(BaseModel):
    contract_id: str
    description: Optional[str] = None
    obligated_amount: float
    signed_date: date
    award_type: Optional[str] = None


class Contract(ContractBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    vendor_id: Optional[UUID] = None
    agency_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


# --- API Response Models ---
class VendorStats(BaseModel):
    total_awards: int
    total_obligated_amount: float
    top_agencies: List[Dict[str, Any]]
    award_count_by_year: List[Dict[str, Any]]


class AgencyStats(BaseModel):
    total_awards: int
    total_obligated_amount: float
    top_vendors: List[Dict[str, Any]]
    spending_by_year: List[Dict[str, Any]]


class PaginatedResponse(BaseModel):
    total: int
    page: int
    size: int
    items: List[Any]


# --- Graph Models (Cytoscape.js compatible) ---
class GraphNodeData(BaseModel):
    id: str
    label: str
    type: str  # 'vendor', 'agency', 'contract'
    properties: Dict[str, Any] = {}


class GraphNode(BaseModel):
    data: GraphNodeData


class GraphEdgeData(BaseModel):
    id: str
    source: str
    target: str
    label: str
    properties: Dict[str, Any] = {}


class GraphEdge(BaseModel):
    data: GraphEdgeData


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]

class CypherQuery(BaseModel):
    query: str
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)
