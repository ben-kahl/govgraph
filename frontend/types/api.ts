export interface Vendor {
  id: string;
  canonical_name: string;
  uei: string | null;
  duns: string | null;
  resolved_by_llm: boolean;
  resolution_confidence: number;
  created_at: string;
  updated_at: string;
}

export interface PaginatedVendors {
  total: number;
  page: number;
  size: number;
  items: Vendor[];
}

export interface Agency {
  id: string;
  name: string;
  agency_code: string | null;
}

export interface PaginatedAgencies {
  total: number;
  page: number;
  size: number;
  items: Agency[];
}

export interface MarketShareEntry {
  canonical_name: string;
  award_count: number;
  total_obligated: number;
  market_share_pct: number;
}

export interface SpendingTimeSeries {
  period: string;
  contract_count: number;
  total_obligated: number;
}

export interface AnomalyEntry {
  canonical_name: string;
  contract_id: string;
  obligated_amount: number;
  avg_amount: number;
  z_score: number;
}

export interface NewEntrant {
  canonical_name: string;
  first_award: string;
  award_count: number;
  total_value: number;
}

export interface SoleSourceFlag {
  agency_name: string;
  sole_vendor: string;
  contracts: number;
  total_spend: number;
}

export interface GraphNode {
  id: string;
  label: string;
  type: 'Vendor' | 'Agency' | 'Contract';
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}
