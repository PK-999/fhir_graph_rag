# Engineering Standards

## General
- Python 3.12+
- TypeScript strict mode
- typed public interfaces
- structured logging
- environment configuration via `.env`, never committed secrets
- no real PHI

## Python
- formatter/linter: Ruff
- type checking: mypy or pyright
- tests: pytest
- use Pydantic models at service boundaries
- pure transformation functions where practical

## TypeScript
- ESLint
- strict TypeScript
- React Server Components by default where useful
- client components only when interaction requires them
- no `any` unless documented

## Testing pyramid

### Unit
- deterministic ID generation
- demographics generation
- encounter timing
- clinical scenario state transitions
- resource reference extraction
- graph mapping

### Contract
- API response schemas
- FHIR resource serialization
- graph canonical schema

### Integration
- HAPI FHIR transaction load
- Neo4j ingestion
- pipeline reconciliation

### End-to-end
Minimum:
1. launch app
2. search patient
3. open Patient 360
4. expand graph
5. build cohort
6. execute AI query and see evidence

## Synthetic-data gates
CI must fail when:
- a dangling reference exists;
- patient count differs from configured sample for test fixture;
- encounter count is outside configured bounds;
- duplicate IDs exist;
- deterministic snapshot/hash differs unexpectedly.

## Database rules
- parameterized queries only
- migrations checked into source control
- Neo4j constraints created before bulk load
- PostgreSQL schema migrations are versioned

## Security
- synthetic-data banner in UI
- never log secrets
- never log full payloads by default
- AI database credentials must be read-only
- export endpoints require explicit user action

## Performance targets for demo
On development hardware:
- Patient search p95 < 500 ms
- Patient graph depth=2 p95 < 1 s for normal patient
- Dashboard summary < 1 s after cached/materialized metrics
- Generate 1,000-patient dataset without manual intervention
