import type { ApiEnvelope, ApiError } from "@gpd/contracts";
import { ApiClientError, EXIT_CODES, type ExitCode } from "@gpd/api-client";

export function createSuccessEnvelope<T>(
  data: T,
  warnings: string[] = []
): ApiEnvelope<T> {
  return {
    ok: true,
    data,
    warnings,
    error: null,
  };
}

export function createErrorEnvelope(
  error: unknown,
  warnings: string[] = []
): { envelope: ApiEnvelope<null>; exitCode: ExitCode } {
  if (error instanceof ApiClientError) {
    const errorObj: ApiError = {
      code: error.code,
      message: error.message,
      retryable: error.retryable,
      ...(error.fields ? { fields: error.fields } : {}),
    };
    const combinedWarnings = [
      ...warnings,
      ...(error.envelope?.warnings ?? []),
    ];
    return {
      envelope: {
        ok: false,
        data: null,
        warnings: combinedWarnings,
        error: errorObj,
      },
      exitCode: error.exitCode,
    };
  }

  const message = error instanceof Error ? error.message : String(error);
  return {
    envelope: {
      ok: false,
      data: null,
      warnings,
      error: {
        code: "UNEXPECTED_ERROR",
        message,
        retryable: false,
      },
    },
    exitCode: EXIT_CODES.UNEXPECTED,
  };
}
