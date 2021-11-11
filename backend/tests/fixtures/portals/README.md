# Portal parser fixtures

Reduced, sanitized shapes based on public HTML inspected on 11 November 2026:

- Otodom rental search `__NEXT_DATA__.props.pageProps.data.searchAds` and detail `pageProps.ad`.
- Gratka/Morizon rental search `AggregateOffer` JSON-LD and Nuxt `propertyData` reference tables.

Titles, descriptions, listing identities, street labels, photo URLs and contacts were replaced with synthetic values. They are shape/regression fixtures, not a distributable copy of the live listings. The repeated Nuxt property reference and Polish decimal-comma regression are intentional. Full research captures and the live catalog stay in ignored `.local/` storage.
