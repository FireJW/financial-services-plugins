export function buildResponseEndpointCandidates(baseUrl, wireApi) {
  if (wireApi !== "responses") {
    throw new Error(`Unsupported wire_api: ${wireApi}`);
  }

  const normalizedBase = normalizeBaseUrl(baseUrl);
  const candidates = [joinUrl(normalizedBase, "responses")];

  if (!/\/v\d+$/i.test(normalizedBase)) {
    candidates.push(joinUrl(normalizedBase, "v1/responses"));
  }

  return uniqueStrings(candidates);
}

export function extractResponseOutputText(payload) {
  const fragments = [];
  collectTextFragments(payload, fragments);
  const joined = uniqueStrings(fragments.map((fragment) => fragment.trim()).filter(Boolean)).join(
    "\n"
  );

  if (!joined) {
    throw new Error("Responses API returned no textual output");
  }

  return joined;
}

export async function callResponsesApi(provider, prompt, options = {}) {
  const fetchImpl = options.fetchImpl ?? globalThis.fetch;
  if (typeof fetchImpl !== "function") {
    throw new Error("A fetch implementation is required to call the LLM provider");
  }

  const requestBody = {
    model: provider.model,
    input: prompt
  };
  const endpoints = buildResponseEndpointCandidates(provider.baseUrl, provider.wireApi);
  let lastError = null;

  for (let index = 0; index < endpoints.length; index += 1) {
    const endpoint = endpoints[index];

    try {
      const response = await fetchImpl(endpoint, {
        method: "POST",
        headers: buildHeaders(provider),
        body: JSON.stringify(requestBody),
        signal: options.signal
      });

      const responseText = await response.text();
      if (!response.ok) {
        lastError = new Error(
          `Responses API ${response.status} at ${endpoint}: ${truncate(responseText, 240)}`
        );
        if (response.status === 404 && index < endpoints.length - 1) {
          continue;
        }
        throw lastError;
      }

      let payload;
      try {
        payload = JSON.parse(responseText);
      } catch (error) {
        throw new Error(
          `Responses API returned non-JSON content at ${endpoint}: ${truncate(responseText, 240)}`
        );
      }

      return {
        endpoint,
        requestBody,
        payload,
        outputText: extractResponseOutputText(payload)
      };
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
      if (index < endpoints.length - 1) {
        continue;
      }
    }
  }

  throw lastError || new Error("Responses API request failed");
}

function buildHeaders(provider) {
  const headers = {
    "content-type": "application/json"
  };

  if (provider.apiKey) {
    headers.authorization = `Bearer ${provider.apiKey}`;
  }

  return headers;
}

function collectTextFragments(node, fragments) {
  if (typeof node === "string") {
    fragments.push(node);
    return;
  }

  if (!node || typeof node !== "object") {
    return;
  }

  if (typeof node.output_text === "string") {
    fragments.push(node.output_text);
  }

  if (
    typeof node.text === "string" &&
    (!node.type || node.type === "text" || node.type === "output_text")
  ) {
    fragments.push(node.text);
  }

  if (Array.isArray(node.output)) {
    for (const item of node.output) {
      collectTextFragments(item, fragments);
    }
  }

  if (Array.isArray(node.content)) {
    for (const item of node.content) {
      collectTextFragments(item, fragments);
    }
  }
}

function normalizeBaseUrl(baseUrl) {
  return String(baseUrl ?? "").trim().replace(/\/+$/, "");
}

function joinUrl(baseUrl, suffix) {
  const normalizedBase = `${normalizeBaseUrl(baseUrl)}/`;
  return new URL(suffix.replace(/^\/+/, ""), normalizedBase).toString();
}

function truncate(value, maxLength) {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength)}...`;
}

function uniqueStrings(values) {
  return [...new Set(values)];
}
