import { api } from "./api";

export type PaymentProvider = "payme" | "click";

export type PaymentStatus = "pending" | "paid" | "cancelled" | "failed";

export interface Payment {
  id: number;
  provider: PaymentProvider;
  status: PaymentStatus;
  plan: string;
  amount_uzs: number;
  payment_url: string | null;
  paid_at: string | null;
  created_at: string;
}

export async function startCheckout(
  planCode: string,
  provider: PaymentProvider,
  returnPath?: string
): Promise<Payment> {
  return api<Payment>("/payments/checkout/", {
    method: "POST",
    body: JSON.stringify({
      plan_code: planCode,
      provider,
      // Locale-prefixed return path: without it the gateway sends the user
      // back to /premium/payment/{id}/ and the language resets to uz.
      ...(returnPath ? { return_path: returnPath } : {}),
    }),
  });
}

export async function fetchPayment(id: number | string): Promise<Payment> {
  return api<Payment>(`/payments/${id}/`);
}
