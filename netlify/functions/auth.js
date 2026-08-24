// Minimal GitHub OAuth provider for Decap CMS's "github" backend.
// Step 1 (no ?code): redirect the popup to GitHub's authorize page.
// Step 2 (?code=...): exchange the code for a token, then hand it back
// to the admin panel via the postMessage handshake Decap CMS expects.

exports.handler = async (event) => {
  const { code } = event.queryStringParameters || {};
  const clientId = process.env.GITHUB_CLIENT_ID;
  const clientSecret = process.env.GITHUB_CLIENT_SECRET;
  const siteUrl = process.env.URL || `https://${event.headers.host}`;
  const redirectUri = `${siteUrl}/.netlify/functions/auth`;

  if (!clientId || !clientSecret) {
    return {
      statusCode: 500,
      body: "Missing GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET environment variables.",
    };
  }

  if (!code) {
    const authorizeUrl =
      `https://github.com/login/oauth/authorize` +
      `?client_id=${encodeURIComponent(clientId)}` +
      `&redirect_uri=${encodeURIComponent(redirectUri)}` +
      `&scope=repo`;
    return {
      statusCode: 302,
      headers: { Location: authorizeUrl },
    };
  }

  const tokenRes = await fetch("https://github.com/login/oauth/access_token", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ client_id: clientId, client_secret: clientSecret, code, redirect_uri: redirectUri }),
  });
  const tokenData = await tokenRes.json();

  if (!tokenRes.ok || tokenData.error || !tokenData.access_token) {
    const message = `authorization:github:error:${JSON.stringify({
      message: tokenData.error_description || "GitHub OAuth exchange failed",
    })}`;
    return {
      statusCode: 401,
      headers: { "Content-Type": "text/html" },
      body: renderHandshakePage(message),
    };
  }

  const successMessage = `authorization:github:success:${JSON.stringify({
    token: tokenData.access_token,
    provider: "github",
  })}`;

  return {
    statusCode: 200,
    headers: { "Content-Type": "text/html" },
    body: renderHandshakePage(successMessage),
  };
};

function renderHandshakePage(message) {
  return `<!doctype html>
<html><body>
<script>
(function() {
  function receiveMessage(e) {
    window.opener.postMessage(
      ${JSON.stringify(message)},
      e.origin
    );
    window.removeEventListener("message", receiveMessage, false);
  }
  window.addEventListener("message", receiveMessage, false);
  window.opener.postMessage("authorizing:github", "*");
})();
</script>
</body></html>`;
}
