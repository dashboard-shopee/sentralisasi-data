const encoder = new TextEncoder();

async function getHmacKey(secret: string): Promise<CryptoKey> {
  const secretKeyData = encoder.encode(secret);
  return await crypto.subtle.importKey(
    "raw",
    secretKeyData,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"]
  );
}

function base64UrlEncode(str: string | Uint8Array): string {
  let binStr = "";
  if (typeof str === "string") {
    binStr = btoa(unescape(encodeURIComponent(str)));
  } else {
    binStr = btoa(String.fromCharCode(...str));
  }
  return binStr.replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
}

function base64UrlDecode(str: string): string {
  let base64 = str.replace(/-/g, "+").replace(/_/g, "/");
  while (base64.length % 4) {
    base64 += "=";
  }
  return decodeURIComponent(escape(atob(base64)));
}

export async function signSession(payload: any, secret: string, durationSeconds: number): Promise<string> {
  const header = { alg: "HS256", typ: "JWT" };
  const exp = Math.floor(Date.now() / 1000) + durationSeconds;
  const fullPayload = { ...payload, exp };

  const headerEncoded = base64UrlEncode(JSON.stringify(header));
  const payloadEncoded = base64UrlEncode(JSON.stringify(fullPayload));

  const dataToSign = `${headerEncoded}.${payloadEncoded}`;
  const key = await getHmacKey(secret);
  const signatureBuffer = await crypto.subtle.sign(
    "HMAC",
    key,
    encoder.encode(dataToSign)
  );
  
  const signatureEncoded = base64UrlEncode(new Uint8Array(signatureBuffer));
  return `${dataToSign}.${signatureEncoded}`;
}

export async function verifySession(token: string, secret: string): Promise<any | null> {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;

    const [headerEncoded, payloadEncoded, signatureEncoded] = parts;
    const dataToVerify = `${headerEncoded}.${payloadEncoded}`;

    const key = await getHmacKey(secret);
    
    // Decode signature
    const signatureBin = atob(signatureEncoded.replace(/-/g, "+").replace(/_/g, "/"));
    const signatureBytes = new Uint8Array(signatureBin.length);
    for (let i = 0; i < signatureBin.length; i++) {
      signatureBytes[i] = signatureBin.charCodeAt(i);
    }

    const isValid = await crypto.subtle.verify(
      "HMAC",
      key,
      signatureBytes,
      encoder.encode(dataToVerify)
    );

    if (!isValid) return null;

    const payload = JSON.parse(base64UrlDecode(payloadEncoded));
    const now = Math.floor(Date.now() / 1000);
    if (payload.exp && payload.exp < now) {
      return null; // Expired
    }

    return payload;
  } catch (e) {
    console.error("verifySession Error:", e);
    return null;
  }
}
