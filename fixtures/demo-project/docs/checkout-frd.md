# Checkout Functional Requirements Document (FRD)

## API Specification
- **Endpoint**: `POST /api/v1/checkout/pay`
- **Request Body**:
  ```json
  {
    "card_token": "tok_12345",
    "amount": 9900,
    "currency": "USD",
    "order_id": "ord_98765"
  }
  ```
- **Responses**:
  - `200 OK`: `{"status": "success", "transaction_id": "tx_abc"}`
  - `400 Bad Request`: `{"error": "payment_method_invalid", "detail": "Card expired"}`
  - `500 Server Error`: `{"error": "payment_gateway_down"}`

## State Management & Transitions
1. **Idle**: Pay button enabled, loading indicator hidden.
2. **Submitting**:
   - Button text: "Processing..."
   - Spinner: active (`loading = true`)
   - Inputs: disabled to prevent duplicate submissions
3. **Failure Transition**:
   - `loading` must reset to `false` in `finally` block or on catching payment errors.
   - When API returns `400 payment_method_invalid`, display banner:
     "Card expired, please choose another payment method".
   - Unfreeze checkout button and allow user to update card details.

## Error Normalization
- All payment errors returned by the payment gateway must be normalized inside `PaymentService` (`src/payment/payment-service.ts`) before propagating to UI components (`src/checkout/payment-errors.ts`).
- Specifically: HTTP 400 `payment_method_invalid` maps to `ExpiredPaymentMethodError`.
