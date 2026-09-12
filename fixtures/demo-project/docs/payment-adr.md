# ADR-004: Payment Error Normalization in PaymentService

## Status
Accepted

## Context
When processing checkout transactions, various payment gateways and endpoints return diverse error formats, status codes, and error strings. Handling raw HTTP responses directly inside UI components has led to edge cases where loading indicators never terminate (infinite spinners) when receiving 400-series errors like `payment_method_invalid`.

## Decision
1. **Centralized Normalization**: All payment gateway error responses must be caught and normalized inside `PaymentService` (`src/payment/payment-service.ts`).
2. **Domain Errors**: Normalized errors must instantiate typed domain error classes defined in `src/checkout/payment-errors.ts`.
3. **Specific Mappings**:
   - HTTP 400 with error code `payment_method_invalid` must be normalized to `ExpiredPaymentMethodError`.
   - Transient 503 or network drops must be normalized to `PaymentNetworkError`.
4. **UI Safety**: The UI layer must only consume normalized domain errors. State management must ensure `loading = false` is always called in `finally` blocks.

## Consequences
- Single location for error translation and logging.
- Reliable UI state transitions and banner error messaging.
- Avoids duplicated error parsing across checkout steps.
