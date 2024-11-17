# Q13 listing costs and primary actions

Implemented and locally reviewed 2026-11-17. Details lead with title and stated costs, followed by save, eligible owner messaging or active provider actions before photos and long descriptions/history. Reports are a quieter secondary action. Costs explicitly distinguish base rent, building fees and known costs; an unknown fee is not zero and utilities are not claimed included. Cards label the headline price as base rent and use a more legible fee caption.

Node24 typecheck passed. `q13-hierarchy-20261117` passed 2/2 desktop/mobile checks for unknown/zero fees, 390px and 200% text, primary-action ordering, provider actions and unavailable states. `q13-owner-20261117` passed both complete owner/renter publishing, messaging and withdrawal journeys. Parent inspected `docs/previews/quality/q13-actions.png`. No pricing algorithm, ownership-verification claim or overlay was introduced.
