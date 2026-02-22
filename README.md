# ppi

## Retailer config extraction styles

The runner supports two extraction styles:

1. **Explicit `extract` flow action** (preferred).
2. **Legacy top-level blocks**: `pricing`, `discount`, and `unit_price`.

### Explicit flow style

```yaml
retailers:
  ybitan:
    base_url: "https://www.ybitan.co.il"
    goto_wait_until: "domcontentloaded"
    flow:
      - action: goto
        url: "{base_url}/search/{product_id}"
      - action: retry
        limit: 3
      - action: wait_for_selector
        selector: ".sp-product-price"
        timeout_ms: 30000
        state: "visible"
      - action: extract
        fields:
          final_price:
            selectors_priority:
              - 'meta[itemprop="price"]::attr(content)'
              - "span.sale-price"
              - "span.regular-price"
              - "span.price"
          discount:
            selector: "span.sale-price"
            optional: true
            discounted_price_override: false
          unit_price:
            selector: "span.normalize-price"
            optional: true
```

### Legacy style (backward compatible)

```yaml
retailers:
  ybitan:
    base_url: "https://www.ybitan.co.il"
    goto_wait_until: "domcontentloaded"
    flow:
      - action: goto
        url: "{base_url}/search/{product_id}"
      - action: retry
        limit: 3
      - action: wait_for_selector
        selector: ".sp-product-price"

    pricing:
      final_price:
        selectors_priority:
          - 'meta[itemprop="price"]::attr(content)'
          - "span.price"
    discount:
      selector: "span.sale-price"
      optional: true
    unit_price:
      selector: "span.normalize-price"
      optional: true
```

## Precedence rules

- If at least one `extract` action exists in `flow`, extraction is driven by `extract` actions only.
- If no `extract` action exists, the runner auto-generates a backward-compatible final `extract` step from legacy `pricing`/`discount`/`unit_price` blocks.
- For field specs, exactly one of `selector` or `selectors_priority` must be set.

## Selector behavior

- `::attr(name)` selectors extract element attributes.
- Other selectors extract text content.
- Extracted values are trimmed and normalize NBSP characters.
- Priority selector lists return the first non-empty extracted value.


## Retries

- Add a `retry` action to each retailer flow to control attempts per URL.
- `retry.limit` sets the max number of tries (default: `1` when omitted).
- Output CSV includes a `tries` column with the number of attempts used for each row.
