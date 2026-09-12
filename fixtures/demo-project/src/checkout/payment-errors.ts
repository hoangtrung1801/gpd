export class PaymentError extends Error {
  public readonly code: string;
  public readonly userMessage: string;

  constructor(code: string, message: string, userMessage: string) {
    super(message);
    this.name = "PaymentError";
    this.code = code;
    this.userMessage = userMessage;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class ExpiredPaymentMethodError extends PaymentError {
  constructor(detail?: string) {
    super(
      "payment_method_invalid",
      detail || "Payment method is invalid or expired",
      "Card expired, please choose another payment method"
    );
    this.name = "ExpiredPaymentMethodError";
  }
}

export class PaymentNetworkError extends PaymentError {
  constructor(detail?: string) {
    super(
      "payment_network_error",
      detail || "Payment gateway communication failure",
      "Network connection issue. Please retry in a few moments."
    );
    this.name = "PaymentNetworkError";
  }
}

export class PaymentDeclinedError extends PaymentError {
  constructor(detail?: string) {
    super(
      "card_declined",
      detail || "Card transaction declined by issuer",
      "Your card was declined. Please try another card."
    );
    this.name = "PaymentDeclinedError";
  }
}
