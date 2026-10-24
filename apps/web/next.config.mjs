/** Security headers (AWS-04). The proxy (Caddy) also redirects HTTP to HTTPS. */
const devEval = process.env.NODE_ENV === "production" ? "" : " 'unsafe-eval'";
// Sign out posts a form and is answered with a redirect to Cognito's logout page. Browsers apply form-action
// to that redirect too, so Cognito (and only Cognito) is allowed as a form destination.
const formAction = "'self' https://*.amazoncognito.com";
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
  {
    key: "Content-Security-Policy",
    value: `default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'${devEval}; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action ${formAction}`,
  },
];

export default {
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};
