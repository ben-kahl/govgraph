# GovGraph Analysis Techniques

A reference of analytical capabilities available across PostgreSQL and Neo4j, mapped to client-facing use cases. Each section notes which database powers the query and what visualization it supports.

---

## Table of Contents

1. [PostgreSQL — Aggregate & Relational Analytics](#1-postgresql--aggregate--relational-analytics)
2. [Neo4j — Graph & Network Analytics](#2-neo4j--graph--network-analytics)
3. [Hybrid Analyses](#3-hybrid-analyses)
4. [Risk & Anomaly Detection](#4-risk--anomaly-detection)
5. [Frontend Mapping](#5-frontend-mapping)

---

## 1. PostgreSQL — Aggregate & Relational Analytics

PostgreSQL is the source of truth for all financial aggregation, time-series, and ranked list queries. It handles high-cardinality filtering, pagination, and join-heavy workloads efficiently.

### 1.1 Vendor Concentration & Market Share

**Question:** Which vendors dominate federal spending and which agencies are most concentrated?

```sql
SELECT
    v.canonical_name,
    COUNT(c.id)                          AS award_count,
    SUM(c.obligated_amount)              AS total_obligated,
    SUM(c.obligated_amount) * 100.0
        / SUM(SUM(c.obligated_amount)) OVER () AS market_share_pct
FROM vendors v
JOIN contracts c ON c.vendor_id = v.id
GROUP BY v.id, v.canonical_name
ORDER BY total_obligated DESC
LIMIT 25;
```

**Visualization:** Ranked bar chart, treemap of spend share.
**Use case:** "Top Vendors" leaderboard on the main dashboard.

---

### 1.2 Agency Spending Over Time

**Question:** How does an agency's spending trend month-over-month or year-over-year?

```sql
SELECT
    a.agency_name,
    DATE_TRUNC('month', c.signed_date)   AS period,
    COUNT(c.id)                          AS contract_count,
    SUM(c.obligated_amount)              AS total_obligated
FROM contracts c
JOIN agencies a ON a.id = c.agency_id
WHERE a.id = :agency_id
GROUP BY a.agency_name, period
ORDER BY period;
```

**Visualization:** Line or area chart.
**Use case:** Agency detail page — spending history panel.

---

### 1.3 Award Type Distribution

**Question:** What mix of contract types (A, B, C, D, IDV) does an agency or vendor use?

```sql
SELECT
    award_type,
    COUNT(*)               AS count,
    SUM(obligated_amount)  AS total_value
FROM contracts
WHERE vendor_id = :vendor_id   -- or agency_id = :agency_id
GROUP BY award_type
ORDER BY total_value DESC;
```

**Visualization:** Donut or pie chart.
**Use case:** Vendor profile — "Contract Type Breakdown."

---

### 1.4 Vendor–Agency Relationship Matrix

**Question:** Which vendors receive the most awards from which agencies?

```sql
SELECT
    v.canonical_name  AS vendor,
    a.agency_name     AS agency,
    COUNT(c.id)       AS awards,
    SUM(c.obligated_amount) AS total
FROM contracts c
JOIN vendors v  ON v.id = c.vendor_id
JOIN agencies a ON a.id = c.agency_id
GROUP BY v.canonical_name, a.agency_name
HAVING SUM(c.obligated_amount) > 1000000
ORDER BY total DESC;
```

**Visualization:** Heatmap, sortable matrix table.
**Use case:** Supply chain overview — which agencies drive which vendor revenues.

---

### 1.5 Agency Spending Hierarchy (Parent vs. Sub-Agency)

**Question:** How does spending break down across the sub-agency hierarchy within a department?

```sql
WITH RECURSIVE agency_tree AS (
    SELECT id, agency_name, parent_agency_id, 0 AS depth
    FROM agencies
    WHERE parent_agency_id IS NULL

    UNION ALL

    SELECT a.id, a.agency_name, a.parent_agency_id, t.depth + 1
    FROM agencies a
    JOIN agency_tree t ON t.id = a.parent_agency_id
)
SELECT
    t.agency_name,
    t.depth,
    COUNT(c.id)              AS awards,
    SUM(c.obligated_amount)  AS total_obligated
FROM agency_tree t
LEFT JOIN contracts c ON c.agency_id = t.id
GROUP BY t.id, t.agency_name, t.depth
ORDER BY t.depth, total_obligated DESC NULLS LAST;
```

**Visualization:** Sunburst chart, collapsible tree.
**Use case:** Agency explorer — drill down from DOD → Army → specific command.

---

### 1.6 Prime vs. Subcontract Flow

**Question:** What proportion of a prime vendor's awarded value flows down to subcontractors?

```sql
SELECT
    v.canonical_name                            AS prime_vendor,
    SUM(c.obligated_amount)                     AS prime_value,
    SUM(sc.subcontract_amount)                  AS sub_value,
    ROUND(
        SUM(sc.subcontract_amount) * 100.0
        / NULLIF(SUM(c.obligated_amount), 0), 2
    )                                           AS subcontract_pct
FROM vendors v
JOIN contracts c    ON c.vendor_id = v.id
LEFT JOIN subcontracts sc ON sc.prime_vendor_id = v.id
GROUP BY v.id, v.canonical_name
HAVING SUM(c.obligated_amount) > 0
ORDER BY prime_value DESC;
```

**Visualization:** Stacked bar (prime vs. sub), Sankey diagram.
**Use case:** Supply chain panel — "How much flows downstream?"

---

### 1.7 Contract Award Velocity

**Question:** Is a vendor winning contracts at an accelerating or decelerating pace?

```sql
SELECT
    DATE_TRUNC('quarter', signed_date) AS quarter,
    COUNT(*)                           AS awards,
    SUM(obligated_amount)              AS total,
    AVG(obligated_amount)              AS avg_award_size
FROM contracts
WHERE vendor_id = :vendor_id
GROUP BY quarter
ORDER BY quarter;
```

**Visualization:** Line chart with trend line overlay.
**Use case:** Vendor detail page — momentum indicator.

---

### 1.8 Agency Vendor Diversity (Herfindahl Index)

**Question:** Is an agency over-concentrated in a single vendor (potential lock-in risk)?

```sql
WITH vendor_share AS (
    SELECT
        agency_id,
        vendor_id,
        SUM(obligated_amount) AS vendor_total,
        SUM(SUM(obligated_amount)) OVER (PARTITION BY agency_id) AS agency_total
    FROM contracts
    GROUP BY agency_id, vendor_id
)
SELECT
    a.agency_name,
    ROUND(SUM(POWER(vendor_total / agency_total, 2))::numeric, 4) AS hhi
FROM vendor_share vs
JOIN agencies a ON a.id = vs.agency_id
GROUP BY a.id, a.agency_name
ORDER BY hhi DESC;
```

HHI approaching 1.0 = monopoly supplier; near 0 = highly competitive.

**Visualization:** Ranked table with conditional color coding (green/yellow/red).
**Use case:** Risk dashboard — "Vendor Concentration Risk."

---

### 1.9 Entity Resolution Quality Metrics

**Question:** What percentage of contracts are resolved by each tier, and where is confidence low?

```sql
SELECT
    resolution_method,
    COUNT(*)                          AS contract_count,
    ROUND(AVG(resolution_confidence) * 100, 2) AS avg_confidence_pct,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER ()  AS share_pct
FROM contracts
GROUP BY resolution_method
ORDER BY contract_count DESC;
```

**Visualization:** Pie chart, metric cards.
**Use case:** Admin/data quality panel.

---

## 2. Neo4j — Graph & Network Analytics

Neo4j excels at relationship traversal, influence scoring, and multi-hop supply chain analysis. These queries are impractical or prohibitively slow in SQL.

### 2.1 Vendor Influence — PageRank

**Question:** Which vendors are most central to the federal procurement graph (connected through many agencies and contracts)?

```cypher
CALL gds.pageRank.stream('vendor-contract-graph', {
    dampingFactor: 0.85,
    maxIterations: 20
})
YIELD nodeId, score
MATCH (n) WHERE id(n) = nodeId AND n:Vendor
RETURN n.canonicalName AS vendor, score
ORDER BY score DESC
LIMIT 20;
```

Requires a GDS graph projection. Alternatively, approximate with degree counting:

```cypher
MATCH (v:Vendor)-[:AWARDED]->(c:Contract)
WITH v, COUNT(c) AS contract_count, SUM(c.obligatedAmount) AS total_value
MATCH (v)-[:AWARDED]->(c2:Contract)<-[:AWARDED_CONTRACT]-(a:Agency)
WITH v, contract_count, total_value, COUNT(DISTINCT a) AS agency_count
RETURN v.canonicalName, contract_count, total_value, agency_count
ORDER BY agency_count DESC, total_value DESC
LIMIT 25;
```

**Visualization:** Graph with node sizes scaled to score.
**Use case:** "Most influential vendors" — top of the network graph.

---

### 2.2 Supply Chain Depth — Multi-Hop Subcontracting

**Question:** How many tiers deep does a prime vendor's supply chain go, and who are the Tier-2/3 subcontractors?

```cypher
MATCH path = (prime:Vendor {id: $vendor_id})-[:SUBCONTRACTED*1..3]->(sub:Vendor)
RETURN
    prime.canonicalName AS prime,
    [node IN nodes(path) | node.canonicalName] AS chain,
    length(path) AS tier_depth,
    last(relationships(path)).amount AS contract_value
ORDER BY tier_depth, contract_value DESC;
```

**Visualization:** Hierarchical tree graph / force-directed radial layout.
**Use case:** Vendor detail — "Supply Chain" tab showing downstream dependencies.

---

### 2.3 Shared Agency Connections (Vendor Co-occurrence)

**Question:** Which vendor pairs are awarded contracts by the same agencies, suggesting they compete or complement each other in the same market?

```cypher
MATCH (v1:Vendor)-[:AWARDED]->(c1:Contract)<-[:AWARDED_CONTRACT]-(a:Agency)
      -[:AWARDED_CONTRACT]->(c2:Contract)<-[:AWARDED]-(v2:Vendor)
WHERE v1 <> v2 AND id(v1) < id(v2)
WITH v1, v2, COUNT(DISTINCT a) AS shared_agencies
WHERE shared_agencies >= 3
RETURN v1.canonicalName, v2.canonicalName, shared_agencies
ORDER BY shared_agencies DESC
LIMIT 30;
```

**Visualization:** Secondary graph layer — dashed edges between competing vendors.
**Use case:** Market analysis — "Peer vendors" panel on a vendor's detail page.

---

### 2.4 Agency Subcontractor Exposure

**Question:** Through subcontracting chains, which smaller vendors does an agency indirectly depend on?

```cypher
MATCH (a:Agency)-[:AWARDED_CONTRACT]->(c:Contract)<-[:AWARDED]-(prime:Vendor)
      -[:SUBCONTRACTED*1..2]->(sub:Vendor)
WHERE a.id = $agency_id
  AND sub <> prime
RETURN
    sub.canonicalName AS subcontractor,
    COUNT(DISTINCT prime) AS connected_primes,
    SUM(last([(prime)-[r:SUBCONTRACTED]->(sub) | r.amount])) AS estimated_exposure
ORDER BY connected_primes DESC, estimated_exposure DESC;
```

**Visualization:** Expanded graph from the agency node outward.
**Use case:** Agency deep-dive — "Indirect Vendor Exposure."

---

### 2.5 Shortest Path Between Two Vendors

**Question:** Is there a relationship chain connecting two vendors through shared contracts, agencies, or subcontracts?

```cypher
MATCH (v1:Vendor {id: $vendor_id_1}), (v2:Vendor {id: $vendor_id_2})
MATCH path = shortestPath((v1)-[*..6]-(v2))
RETURN path, length(path) AS hops,
       [n IN nodes(path) | coalesce(n.canonicalName, n.agencyName, n.contractId)] AS node_labels;
```

**Visualization:** Highlighted path in the main graph canvas.
**Use case:** OSINT feature — "Find Connection" between any two entities.

---

### 2.6 Community Detection (Vendor Ecosystems)

**Question:** Do natural vendor clusters emerge around specific agencies or contract types?

```cypher
-- Requires Neo4j GDS Louvain algorithm
CALL gds.louvain.stream('procurement-graph')
YIELD nodeId, communityId
MATCH (n) WHERE id(n) = nodeId AND n:Vendor
RETURN communityId, collect(n.canonicalName)[..10] AS sample_vendors, count(*) AS size
ORDER BY size DESC
LIMIT 10;
```

Without GDS, approximate by shared agency clustering:

```cypher
MATCH (a:Agency)-[:AWARDED_CONTRACT]->(c:Contract)<-[:AWARDED]-(v:Vendor)
WITH a, collect(DISTINCT v.canonicalName)[..5] AS top_vendors, count(DISTINCT v) AS vendor_count
WHERE vendor_count BETWEEN 5 AND 50
RETURN a.agencyName, top_vendors, vendor_count
ORDER BY vendor_count DESC;
```

**Visualization:** Color-coded node clusters on the graph.
**Use case:** "Ecosystem" view — group vendors by market segment.

---

### 2.7 Hub-and-Spoke Subcontractor Identification

**Question:** Which vendors act as intermediary hubs, receiving prime awards and distributing extensively to subcontractors?

```cypher
MATCH (prime:Vendor)-[r:SUBCONTRACTED]->(sub:Vendor)
WITH prime,
     COUNT(DISTINCT sub)   AS sub_count,
     SUM(r.amount)         AS total_passed_down
WHERE sub_count >= 5
RETURN prime.canonicalName AS hub_vendor, sub_count, total_passed_down,
       prime.totalContractValue AS prime_value,
       ROUND(total_passed_down * 100.0 / prime.totalContractValue, 2) AS passthrough_pct
ORDER BY sub_count DESC;
```

**Visualization:** Node sizing by `sub_count`; a distinct "hub" icon/shape.
**Use case:** Supply chain risk — identify single points of failure in subcontracting chains.

---

### 2.8 Agency Procurement Network Ego Graph

**Question:** Show all vendors, contracts, and sub-agencies connected to a given agency within N hops.

```cypher
MATCH (a:Agency {id: $agency_id})
CALL apoc.path.subgraphAll(a, {
    maxLevel: 2,
    relationshipFilter: 'AWARDED_CONTRACT>|<AWARDED|SUBAGENCY_OF|<FUNDED'
}) YIELD nodes, relationships
RETURN nodes, relationships;
```

Without APOC:

```cypher
MATCH (a:Agency {id: $agency_id})-[:AWARDED_CONTRACT]->(c:Contract)<-[:AWARDED]-(v:Vendor)
OPTIONAL MATCH (v)-[:SUBCONTRACTED]->(sub:Vendor)
OPTIONAL MATCH (child:Agency)-[:SUBAGENCY_OF]->(a)
RETURN a, c, v, sub, child LIMIT 200;
```

**Visualization:** Full graph canvas centered on the agency node.
**Use case:** Agency detail page — "Network" tab.

---

## 3. Hybrid Analyses

These combine a PostgreSQL aggregate with a Neo4j traversal, either via two API calls merged in the backend or a dedicated endpoint.

### 3.1 High-Value Vendor + Network Centrality Leaderboard

1. **PostgreSQL:** Pull top 100 vendors by `total_obligated_amount`.
2. **Neo4j:** For each, count `DISTINCT` agencies connected and subcontractor depth.
3. **Merge:** Rank by a composite score: `(normalized_spend * 0.6) + (agency_diversity * 0.4)`.

**Visualization:** Sortable table with a mini graph icon per row; click to open full graph.

---

### 3.2 Contract Timeline + Relationship History

1. **PostgreSQL:** Pull all contracts for a vendor sorted by `signed_date` (timeline data).
2. **Neo4j:** For each contract, fetch the full relationship context (agency, sub-vendors involved).
3. **Merge:** Animate the network graph as the user scrubs through the timeline.

**Visualization:** Timeline scrubber linked to graph canvas — relationships appear/disappear as the date changes.

---

### 3.3 Agency Budget Allocation → Downstream Supply Chain

1. **PostgreSQL:** Calculate agency's total annual spend and top 10 prime vendors.
2. **Neo4j:** For each prime vendor, traverse `:SUBCONTRACTED` edges to show downstream flow.
3. **Merge:** Sankey diagram — `Agency → Prime Vendors → Subcontractors`.

**Visualization:** Sankey / alluvial chart.

---

### 3.4 Vendor Risk Profile

Combine multiple signals into a risk score for a single vendor:

| Signal | Source | Weight |
|--------|--------|--------|
| % of revenue from single agency | PostgreSQL (HHI) | 30% |
| Number of subcontractors used | Neo4j (SUBCONTRACTED degree) | 20% |
| Resolution confidence average | PostgreSQL | 20% |
| Network centrality (agency count) | Neo4j | 30% |

**Visualization:** Radar/spider chart per vendor.

---

## 4. Risk & Anomaly Detection

### 4.1 Unusual Award Size Spikes (PostgreSQL)

Flag contracts significantly above a vendor's historical average:

```sql
WITH vendor_stats AS (
    SELECT
        vendor_id,
        AVG(obligated_amount)    AS avg_amount,
        STDDEV(obligated_amount) AS stddev_amount
    FROM contracts
    GROUP BY vendor_id
)
SELECT
    v.canonical_name,
    c.contract_id,
    c.obligated_amount,
    vs.avg_amount,
    ROUND((c.obligated_amount - vs.avg_amount) / NULLIF(vs.stddev_amount, 0), 2) AS z_score
FROM contracts c
JOIN vendors v        ON v.id = c.vendor_id
JOIN vendor_stats vs  ON vs.vendor_id = c.vendor_id
WHERE (c.obligated_amount - vs.avg_amount) / NULLIF(vs.stddev_amount, 0) > 3
ORDER BY z_score DESC;
```

**Use case:** "Anomaly" badge on contracts in the UI.

---

### 4.2 New Entrant Detection (PostgreSQL)

Vendors that first appear in the last 90 days with significant awards:

```sql
SELECT
    v.canonical_name,
    MIN(c.signed_date) AS first_award,
    COUNT(c.id)        AS award_count,
    SUM(c.obligated_amount) AS total_value
FROM vendors v
JOIN contracts c ON c.vendor_id = v.id
GROUP BY v.id, v.canonical_name
HAVING MIN(c.signed_date) >= CURRENT_DATE - INTERVAL '90 days'
   AND SUM(c.obligated_amount) > 500000
ORDER BY total_value DESC;
```

**Use case:** "New to market" tag in vendor search results.

---

### 4.3 Single-Supplier Agency Dependency (Neo4j)

Agencies whose contract graph connects to only one vendor for a given contract type — a procurement risk:

```cypher
MATCH (a:Agency)-[:AWARDED_CONTRACT]->(c:Contract {awardType: 'A'})<-[:AWARDED]-(v:Vendor)
WITH a, COUNT(DISTINCT v) AS unique_vendors
WHERE unique_vendors = 1
MATCH (a)-[:AWARDED_CONTRACT]->(c2:Contract)<-[:AWARDED]-(sole:Vendor)
RETURN a.agencyName, sole.canonicalName AS sole_source_vendor,
       COUNT(c2) AS contracts, SUM(c2.obligatedAmount) AS total_spend
ORDER BY total_spend DESC;
```

**Use case:** Risk heatmap — agencies with no competitive bidding.

---

### 4.4 Circular Subcontracting Detection (Neo4j)

Identify subcontracting loops (A primes to B, B subs to C, C subs back to A) — a potential indicator of pass-through fraud:

```cypher
MATCH cycle = (v:Vendor)-[:SUBCONTRACTED*2..4]->(v)
RETURN [n IN nodes(cycle) | n.canonicalName] AS loop_members,
       length(cycle) AS loop_length
LIMIT 20;
```

**Use case:** Fraud detection / compliance panel — flag for manual review.

---

## 5. Frontend Mapping

| Analysis | Page | Primary DB | Chart Type |
|----------|------|-----------|------------|
| Top vendors by spend | Dashboard | PostgreSQL | Bar chart |
| Agency spending over time | Agency detail | PostgreSQL | Line chart |
| Award type distribution | Vendor/Agency detail | PostgreSQL | Donut chart |
| Market share treemap | Dashboard | PostgreSQL | Treemap |
| Agency spending hierarchy | Agency explorer | PostgreSQL | Sunburst |
| Prime vs. sub flow | Vendor detail | PostgreSQL | Stacked bar / Sankey |
| Vendor concentration (HHI) | Risk dashboard | PostgreSQL | Ranked table |
| Resolution quality | Admin panel | PostgreSQL | Pie chart + metrics |
| Vendor influence graph | Main graph canvas | Neo4j | Cytoscape force-directed |
| Supply chain depth | Vendor detail | Neo4j | Radial tree |
| Shared agency peers | Vendor detail | Neo4j | Secondary graph layer |
| Shortest path / find connection | Graph canvas | Neo4j | Highlighted path |
| Community clusters | Graph canvas | Neo4j | Color-coded clusters |
| Hub vendor identification | Supply chain view | Neo4j | Sized nodes |
| Agency ego graph | Agency detail | Neo4j | Subgraph expansion |
| Vendor risk profile | Vendor detail | Both | Radar chart |
| Contract timeline + graph | Vendor detail | Both | Timeline + graph |
| Budget → supply chain flow | Agency detail | Both | Sankey |
| Award size anomalies | Contract list | PostgreSQL | Z-score badge |
| New entrant detection | Vendor search | PostgreSQL | "New" tag |
| Sole-source dependency | Risk dashboard | Neo4j | Risk heatmap |
| Circular subcontracting | Compliance panel | Neo4j | Flagged list |

---

## Notes on API Design

- **PostgreSQL queries** → standard REST endpoints (`/vendors`, `/agencies`, `/analytics/summary`). Add query parameters for filtering and time range.
- **Neo4j queries** → graph endpoints (`/graph/vendor/:id`, `/graph/agency/:id`, `/graph/path`). Return Cytoscape-compatible `{nodes, edges}` format already implemented in `api.py`.
- **Hybrid analyses** → dedicated endpoints that fan out to both DBs and merge results before returning (e.g., `/analytics/vendor/:id/risk-profile`).
- The `/graph/query` raw Cypher endpoint should be **removed before public launch** — use parameterized graph endpoints instead.
