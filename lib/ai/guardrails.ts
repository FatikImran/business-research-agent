export function needsEscalation(reply: string, userMessage: string) {
  const text = `${reply} ${userMessage}`.toLowerCase();
  return ["unknown", "unclear", "cannot confirm", "not enough information", "legal", "fraud"].some((term) =>
    text.includes(term)
  );
}

export function redactUnsafe(input: string) {
  return input.replace(/(api[_-]?key|password|secret)\s*[:=]\s*\S+/gi, "$1:[redacted]");
}
