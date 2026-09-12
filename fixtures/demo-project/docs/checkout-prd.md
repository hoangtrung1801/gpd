# Checkout Flow Product Requirements Document (PRD)

## Overview
The Checkout flow allows customers to purchase selected items by providing payment details, billing information, and confirming their order.

## Problem Statement
When a user submits payment with an invalid or expired card, the system must provide immediate, actionable feedback without leaving the user interface in an ambiguous or unresponsive state.

## Core Requirements
1. **Validation**: All card inputs must be validated before submission.
2. **Payment Processing**: Submissions go to `POST /api/v1/checkout/pay`.
3. **Error Handling**:
   - If payment fails due to an expired or invalid payment method (`payment_method_invalid`), the UI must immediately stop the loading spinner and display a clear error message: "Card expired, please choose another payment method".
   - Under no circumstances should the button remain frozen in a loading state.
4. **Retry Policies**:
   - Fatal errors (e.g., expired card, invalid card number) must not be retried automatically.
   - Transient network errors may be retried up to 2 times with exponential backoff.
5. **Technical Components**:
   - Payment processing: `src/payment/payment-service.ts`
   - Error definitions and UI mapping: `src/checkout/payment-errors.ts`
