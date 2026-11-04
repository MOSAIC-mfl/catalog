# ADR-0005: Access is explicit; public data needs a URL, non-public data needs a way to ask

- Status: proposed (2026-10-30)

## Decision

- `access` (`public` | `restricted` | `internal`) is part of the minimum. An absent value never
  means public.
- `public`: at least one access point has a `url`.
- `restricted` / `internal`: an `access_note` saying how to obtain the data is required; a URL is
  optional.
- Each access point may carry its own `access` when it differs from the record. Example: public
  data with an internal Earth Engine copy.
