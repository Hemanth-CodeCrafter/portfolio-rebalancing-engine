# Entity relationship diagram

```mermaid
erDiagram
  INVESTOR_PROFILE ||--o{ PORTFOLIO : owns
  PORTFOLIO ||--o{ HOLDING : contains
  INSTRUMENT ||--o{ HOLDING : held_as
  INSTRUMENT ||--o{ MARKET_PRICE : priced_by
  PORTFOLIO ||--o{ TARGET_ALLOCATION : targets
  PORTFOLIO ||--o{ REBALANCE_PROPOSAL : receives
  REBALANCE_PROPOSAL ||--o{ TRADE : contains
  INSTRUMENT ||--o{ TRADE : traded
  FEE_SCHEDULE o|--o{ TRADE : prices
  PORTFOLIO o|--o{ CONSTRAINT_RULE : scoped_to
  INSTRUMENT o|--o{ CONSTRAINT_RULE : scoped_to
```

`entity_event` is a polymorphic audit log linked to several entity types by `(entity_type, entity_id)`; it is omitted from the ER diagram because that relationship cannot be expressed as one ordinary FK.
