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


# --- Analytics Response Models ---
class MarketShareEntry(BaseModel):
    canonical_name: str
    award_count: int
    total_obligated: float
    market_share_pct: float


class SpendingTimeSeries(BaseModel):
    period: datetime
    contract_count: int
    total_obligated: float


class AwardTypeBreakdown(BaseModel):
    award_type: Optional[str]
    count: int
    total_value: float


class ConcentrationMetric(BaseModel):
    agency_name: str
    hhi: float


class VelocityEntry(BaseModel):
    quarter: datetime
    awards: int
    total: float
    avg_award_size: float


class SubcontractFlow(BaseModel):
    prime_vendor: str
    prime_value: float
    sub_value: Optional[float]
    subcontract_pct: Optional[float]


class ResolutionQualityEntry(BaseModel):
    resolution_method: Optional[str]
    contract_count: int
    avg_confidence_pct: Optional[float]
    share_pct: float


class AnomalyEntry(BaseModel):
    canonical_name: str
    contract_id: str
    obligated_amount: float
    avg_amount: float
    z_score: float


class NewEntrant(BaseModel):
    canonical_name: str
    first_award: date
    award_count: int
    total_value: float


class HubVendor(BaseModel):
    canonical_name: str
    sub_count: int
    total_passed_down: float
    passthrough_pct: Optional[float]


class SoleSourceFlag(BaseModel):
    agency_name: str
    sole_vendor: str
    contracts: int
    total_spend: float


class CircularChain(BaseModel):
    loop_members: List[str]
    loop_length: int
