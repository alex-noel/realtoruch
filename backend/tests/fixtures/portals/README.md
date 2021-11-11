# Portal parser fixtures

The baseline search and detail files are reduced public-page shapes inspected on 11 November 2026. Otodom supplied Next.js state. Gratka and Morizon supplied search JSON-LD and Nuxt property tables. OLX supplied rendered card links and detail JSON-LD, property parameters and location breadcrumbs in an ordinary Chrome session without sign-in. Scheduled OLX HTTP collection returned 403 and remains disabled.

Titles, descriptions, listing identities, street labels, photo URLs and contacts in the baseline files are synthetic. The two Nuxt detail files use the non-dialable contact canary `000 000 000` or `000000000`. The repeated Nuxt property reference is intentional. City, district and region labels preserve the public location hierarchy. No session data, headers or full captures are included.

The new empty, drift and access pages are synthetic fixtures created and inspected offline on 11 November 2026 in Europe/Warsaw. They contain only the markers and fields needed to exercise the parser. A portal name labels the parser contract being tested. It does not identify the origin of a capture. The detail variants in `test_portals.py` replace or omit only the indicated fields in memory and retain the baseline provenance.

| Scenario | Otodom | Gratka | Morizon | OLX |
| --- | --- | --- | --- | --- |
| Active detail | `otodom-detail.html` | `gratka-detail.html` | `morizon-detail.html` | `olx-detail.html` |
| Changed base rent | Replace `characteristics.price` | Replace `price.amount` | Replace `price.amount` | Replace `offers.price` |
| Explicit unavailable | Set ad status to `inactive` | Set presentation to `ARCHIVED` | Set embedded status to 410 | Set `OutOfStock` with matching Product URL and SKU. Without URL evidence the parser fails closed. |
| No results | Explicit empty Next.js `items` and pagination | Explicit empty rental JSON-LD `offers` | Explicit empty rental JSON-LD `offers` | Unverified empty markup in `olx-empty.html` must fail closed |
| Pagination | Next.js page counters in `otodom-search.html` | Next-page link in `gratka-search.html` | Next-page link in `morizon-search.html` | `Dalej` link in `olx-search.html` |
| Sale | Set `adCategory.type` to `SELL` | Set transaction to `SELL` | Set transaction to `SELL` | Change Product category to `/sprzedaz/` |
| Missing required field | Remove room characteristic | Remove room count reference | Remove room count reference | Remove rendered room-count parameter |
| Challenge or consent | Shared `access-challenge.html` and `consent-interstitial.html` | Same shared interstitials | Same shared interstitials | Same shared interstitials |
| Structural drift | `otodom-drift.html` replaces `items` | `gratka-drift.html` replaces `offers` | `morizon-drift.html` replaces `offers` | `olx-drift.html` supplies an unfamiliar card URL |

All four details are also exercised with foreign currency, fractional PLN with Polish grouping spaces, required rent ranges and optional fees that must remain unknown. The lifecycle tests mock transport and audit the resulting collector logs with synthetic canaries. This matrix supplies no live evidence for empty, removed or blocked pages.
