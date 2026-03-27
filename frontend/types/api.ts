export interface Vendor {
  id: string;
  canonical_name: string;
  uei: string | null;
  duns: string | null;
  resolved_by_llm: boolean;
  resolution_confidence: number;
  created_at: string;
  updated_at: string;
  // Present on list responses (joined from contracts); absent on single-vendor detail
  contract_count?: number;
  total_obligated?: number;
}

export interface PaginatedVendors {
  total: number;
  page: number;
  size: number;
  items: Vendor[];
}

export interface Agency {
  id: string;
  agency_name: string;
  agency_code: string | null;
}

export interface HubVendor {
  canonical_name: string;
  sub_count: number;
  total_passed_down: number;
  passthrough_pct: number | null;
}

export interface PaginatedAgencies {
  total: number;
  page: number;
  size: number;
  items: Agency[];
}

export interface SummaryStats {
  total_vendors: number;
  total_agencies: number;
  total_contracts: number;
  total_obligated_amount: number;
}

export interface AgencyMarketShareEntry {
  agency_name: string;
  award_count: number;
  total_obligated: number;
  market_share_pct: number;
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
  vendor_id: string;
  canonical_name: string;
  contract_id: string;
  obligated_amount: number;
  avg_amount: number;
  z_score: number;
}

export interface NewEntrant {
  vendor_id: string;
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

export interface AwardTypeBreakdown {
  award_type: string | null;
  count: number;
  total_value: number;
}

export interface VelocityEntry {
  quarter: string;
  awards: number;
  total: number;
  avg_award_size: number;
}

export interface AgencyStats {
  total_awards: number;
  total_obligated_amount: number;
  top_vendors: { vendor_id: string; canonical_name: string; amount: number; count: number }[];
  spending_by_year: { year: number; amount: number }[];
}

export interface VendorStats {
  total_awards: number;
  total_obligated_amount: number;
  top_agencies: { agency_id: string; agency_name: string; amount: number; count: number }[];
  award_count_by_year: { year: number; amount: number; count: number }[];
}

export interface ConcentrationMetric {
  agency_name: string;
  hhi: number;
}

export interface CircularChainMember {
  id: string;
  name: string;
}

export interface CircularChain {
  loop_members: CircularChainMember[];
  loop_length: number;
}

export interface GraphNodeData {
  id: string;
  label: string;
  type: 'Vendor' | 'Agency' | 'Contract';
  properties?: Record<string, unknown>;
  /** totalContractValue for Vendor, obligatedAmount for Contract */
  weight?: number;
  /** True when this Agency is a child of another Agency */
  isSubagency?: boolean;
}
export interface GraphNode {
  data: GraphNodeData;
}

export interface GraphEdgeData {
  id: string;
  source: string;
  target: string;
  label: string;
  /** obligatedAmount for contract edges; totalValue for overview edges */
  weight?: number;
}
export interface GraphEdge {
  data: GraphEdgeData;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}
