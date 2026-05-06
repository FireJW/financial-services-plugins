export function decodeUnknownText(input) {
  const buffer = Buffer.isBuffer(input) ? input : Buffer.from(input || "");
  if (buffer.length >= 2) {
    if (buffer[0] === 0xff && buffer[1] === 0xfe) {
      return buffer.subarray(2).toString("utf16le");
    }
    if (buffer[0] === 0xfe && buffer[1] === 0xff) {
      return swapUtf16Bytes(buffer.subarray(2)).toString("utf16le");
    }
  }

  if (looksLikeUtf16Le(buffer)) {
    return buffer.toString("utf16le");
  }

  const utf8 = buffer.toString("utf8");
  if (buffer.length % 2 === 0 && countReplacementChars(utf8) > 0) {
    return buffer.toString("utf16le");
  }

  return utf8;
}

export async function readTextFromStdin(stdin = process.stdin) {
  const chunks = [];
  for await (const chunk of stdin) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return decodeUnknownText(Buffer.concat(chunks));
}

function looksLikeUtf16Le(buffer) {
  if (buffer.length < 4 || buffer.length % 2 !== 0) {
    return false;
  }
  let zeroOddBytes = 0;
  for (let index = 1; index < buffer.length; index += 2) {
    if (buffer[index] === 0) {
      zeroOddBytes += 1;
    }
  }
  return zeroOddBytes >= Math.max(2, Math.floor(buffer.length / 6));
}

function swapUtf16Bytes(buffer) {
  const swapped = Buffer.from(buffer);
  for (let index = 0; index + 1 < swapped.length; index += 2) {
    const left = swapped[index];
    swapped[index] = swapped[index + 1];
    swapped[index + 1] = left;
  }
  return swapped;
}

function countReplacementChars(value) {
  return [...String(value || "")].filter((character) => character === "\uFFFD").length;
}
