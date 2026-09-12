import {
  ExpiredPaymentMethodError,
  PaymentDeclinedError,
  PaymentError,
  PaymentNetworkError,
} from "../checkout/payment-errors.js";

export interface PaymentRequest {
  cardToken: string;
  amount: number;
  currency: string;
  orderId: string;
}

export interface PaymentResult {
  transactionId: string;
  status: "success" | "failed";
  amount: number;
}

export class PaymentService {
  private readonly gatewayUrl: string;

  constructor(gatewayUrl = "/api/v1/checkout/pay") {
    this.gatewayUrl = gatewayUrl;
  }

  /**
   * Process a checkout payment request and normalize gateway errors.
   * Conforms to ADR-004: All gateway errors are normalized inside PaymentService.
   */
  public async processPayment(request: PaymentRequest): Promise<PaymentResult> {
    let response: Response;
    try {
      response = await fetch(this.gatewayUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          card_token: request.cardToken,
          amount: request.amount,
          currency: request.currency,
          order_id: request.orderId,
        }),
      });
    } catch (err) {
      throw new PaymentNetworkError(err instanceof Error ? err.message : String(err));
    }

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      this.normalizeAndThrowError(response.status, errorBody);
    }

    const data = await response.json();
    return {
      transactionId: data.transaction_id,
      status: "success",
      amount: request.amount,
    };
  }

  /**
   * Normalizes raw HTTP gateway responses into typed domain errors.
   */
  public normalizeAndThrowError(statusCode: number, body: Record<string, unknown>): never {
    const errorCode = typeof body.error === "string" ? body.error : "";
    const detail = typeof body.detail === "string" ? body.detail : undefined;

    if (statusCode === 400 && errorCode === "payment_method_invalid") {
      throw new ExpiredPaymentMethodError(detail);
    }

    if (statusCode === 400 && errorCode === "card_declined") {
      throw new PaymentDeclinedError(detail);
    }

    if (statusCode >= 500) {
      throw new PaymentNetworkError(detail || `Server error ${statusCode}`);
    }

    throw new PaymentError(
      errorCode || "payment_failed",
      detail || `Payment processing failed with status ${statusCode}`,
      "An unexpected error occurred during payment. Please try again."
    );
  }
}
