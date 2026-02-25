// Example dashboard queries for DSO graph (Neo4j Cypher)
// Use with Neo4j Browser or API run_list()

// 1. High-risk devices in last 24h
MATCH (d:Device)-[:HAS_RISK_IN]->(r:RiskScore)
WHERE r.window_end >= datetime() - duration('P1D') AND r.level IN ['high', 'medium']
RETURN d.node_id, d.platform, r.score, r.window_end
ORDER BY r.score DESC
LIMIT 100;

// 2. Coordinated spike: devices in same cluster with high risk in same window
MATCH (d:Device)-[:MEMBER_OF]->(c:Cluster)<-[:MEMBER_OF]-(d2:Device)
MATCH (d)-[:HAS_RISK_IN]->(r:RiskScore), (d2)-[:HAS_RISK_IN]->(r2:RiskScore)
WHERE r.window_start = r2.window_start AND r.score >= 0.5 AND r2.score >= 0.5
RETURN c.cluster_id, collect(d.node_id) AS devices, r.window_start;

// 3. Risk propagation path from a device (1..3 hops)
MATCH path = (d:Device {node_id: $device_id})-[:HAS_RISK_IN|PROPAGATES_TO*1..3]->(r:RiskScore)
RETURN path;

// 4. Surveillance summary per subject (non-intrusive, last 24h)
MATCH (d:Device)-[:TRACKED_AS]->(s:SurveillanceSubject)
OPTIONAL MATCH (d)-[:HAS_RISK_IN]->(r:RiskScore)
WHERE r.window_end >= datetime() - duration('P1D')
RETURN s.subject_id, s.label, count(DISTINCT d) AS devices, count(r) AS risk_events, avg(r.score) AS avg_risk;

// 5. Event volume by kind and device (last 6h)
MATCH (d:Device)-[:REPORTS]->(e:Event)
WHERE e.ts >= datetime() - duration('PT6H')
RETURN d.node_id, e.kind, count(e) AS cnt
ORDER BY cnt DESC;

// 6. Clusters created in last 24h with member count
MATCH (c:Cluster)
WHERE c.created_at >= datetime() - duration('P1D')
MATCH (d:Device)-[:MEMBER_OF]->(c)
RETURN c.cluster_id, c.method, c.size, collect(d.node_id) AS members;

// 7. Devices that communicate with high-risk devices
MATCH (high:Device)-[:HAS_RISK_IN]->(r:RiskScore)
WHERE r.score >= 0.7
MATCH (high)-[:COMMUNICATES_WITH]-(other:Device)
RETURN DISTINCT other.node_id, high.node_id AS risk_neighbor;
