export default function (pi: {
  on: (e: string, h: (ev: unknown) => unknown) => void;
}) {
  pi.on("before_provider_request", async (event) => {
    const payload = (event as { payload?: any }).payload;
    const parts = payload?.request?.systemInstruction?.parts;
    if (!Array.isArray(parts)) return undefined;
    for (const part of parts) {
      if (
        typeof part?.text === "string" &&
        part.text.includes("<system-conventions>")
      ) {
        part.text = part.text.replace(
          /<system-conventions>[\s\S]*?<\/system-conventions>\s*/,
          "",
        );
      }
    }
    return payload;
  });
}
